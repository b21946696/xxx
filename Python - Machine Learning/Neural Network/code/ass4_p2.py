# -*- coding: utf-8 -*-
"""ass4-p2.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1KN4hmBBPd6v1aTLDOmduiBdhKa0hxznF
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import random
import torch
import torch.nn as nn
import torchvision
from torchvision import transforms,models
from torch.utils.data import DataLoader
from tqdm.notebook import tqdm_notebook
from IPython.core.display import HTML,display
from tqdm import tqdm
from PIL import Image
from torch.utils.data import DataLoader
from sklearn.metrics import confusion_matrix
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score,classification_report
from sklearn.metrics import precision_recall_fscore_support as score
import seaborn as sns
import cv2 as cv

if torch.cuda.is_available():
    device = torch.device('cuda:0')
    print("Using GPU")
else:
    device = torch.device('cpu')
    print("Using CPU")

TRAIN_PATH='/kaggle/input/vegetable-image-dataset/Vegetable Images/train'
VALIDATION_PATH='/kaggle/input/vegetable-image-dataset/Vegetable Images/validation'
TEST_PATH='/kaggle/input/vegetable-image-dataset/Vegetable Images/test'

#Resize image. 
#Apply CenterCrop which is transformation of crop the image by each direction. 
#ToTensor allows converting images to tensors
RESIZE_DIM=224
train_transform = transforms.Compose([
                                     transforms.Resize(RESIZE_DIM),
                                     transforms.CenterCrop(RESIZE_DIM),
                                     transforms.ToTensor()
])

test_transform = transforms.Compose([
                                     transforms.Resize(RESIZE_DIM),
                                     transforms.CenterCrop(RESIZE_DIM),
                                     transforms.ToTensor()
                                     ])

#Image folder is dataset class that provides a convenient way to load a dataset of images stored in a directory structure 
train_data=torchvision.datasets.ImageFolder(root=TRAIN_PATH,transform=train_transform)
test_data=torchvision.datasets.ImageFolder(root=TEST_PATH,transform=test_transform)
val_data=torchvision.datasets.ImageFolder(root=VALIDATION_PATH,transform=test_transform)

class_names=train_data.classes
class_names

#set batch size
BATCH_SIZE=64
numclass=len(class_names)
numclass

#load the data from the ImageFolder dataset in batches
train_dl=DataLoader(train_data,BATCH_SIZE,shuffle=True,num_workers=0)
val_dl=DataLoader(val_data,BATCH_SIZE,shuffle=True,num_workers=0)
test_dl=DataLoader(test_data,BATCH_SIZE,shuffle=False,num_workers=0)

"""**VGG19 model visualization**"""

# load the model
model = models.vgg19(pretrained=True)

weights = []
layers = []
count = 0 

for i in model.children():
    if type(i) == nn.Sequential:
        for j in i:
                if type(j) == nn.Conv2d:
                    count += 1
                    weights.append(j.weight)
                    layers.append(j)
print("Number of convolutional layers:",count)

# visualize the first conv layer filters
plt.figure(figsize=(20, 17))
for i, filter in enumerate(weights[0]):
    plt.subplot(8, 8, i+1)
    plt.imshow(filter[0, :, :].detach(), cmap='gray')
plt.show()

# read and visualize an image
img = cv.imread(f"/kaggle/input/vegetable-image-dataset/Vegetable Images/test/Bean/0001.jpg")
img = cv.cvtColor(img, cv.COLOR_BGR2RGB)
plt.imshow(img)
plt.show()
# define the transforms
transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])

img = np.array(img)
img = transform(img)
img = img.unsqueeze(0)

results = [layers[0](img)]
for i in range(1, len(layers)):
    results.append(layers[i](results[-1]))

for num in range(len(results)):
    print("-------------------------------------------------------------------------------------------------------")
    print("Conv Layer->",num+1)
    plt.figure(figsize=(8, 8))
    visualize = results[num][0, :, :, :]
    visualize = visualize.data
    for i, filter in enumerate(visualize):
        if i == 4:
            break
        plt.subplot(2, 2, i + 1)
        plt.imshow(filter, cmap='gray')
        
    plt.show()
    plt.close()

"""**Functions:**"""

#For early stopping this class compare validation loss and train loss
class EarlyStopper:
    def __init__(self, min_delta=0):
        self.min_delta = min_delta

    def early_stop(self, validation_loss,train_loss):
        if validation_loss.item() - train_loss.item() >= self.min_delta:
            print("EarlyStopping!")
            return True
        return False

def train(model,EPOCHS,train_loader,valid_loader,lossFn,optimizer,scheduler,BATCH_SIZE,early_stop=False):
    model.to(device)
    
    train_losses=[] 
    val_losses=[]
    
    train_acc=[]
    val_acc=[]
    
    estopper=EarlyStopper(0)
    
    for e in range(0, EPOCHS):
        # set the model as train
        model.train()   

        trainLoss = 0
        trainCorrect = 0
        
        #update learning rate with scheduler 
        scheduler.step()
        
        # Print Learning Rate
        print('Epoch:', e+1,'Learning Rate:', scheduler.get_last_lr())
        
        # loop on train data
        with tqdm(train_loader, unit="batch") as tepoch:
            
            count=0
            for x, y in tepoch:
                count+=1
                tepoch.set_description(f"Epoch {e+1}")
                
                # send the input to the device
                (x, y) = (x.to(device), y.to(device)) 

                #forward step
                pred = model(x) 
                
                #calculate train loss
                loss = lossFn(pred, y) 
                
                #zero out the gradients
                optimizer.zero_grad()
                #backpropagation step
                loss.backward()
                #optimizer step
                optimizer.step()
                #add the loss to the total training loss
                trainLoss += loss
                
                #calculate the number of correct predictions
                trainCorrect += (pred.argmax(1) == y).type(torch.float).sum().item()
                correct = (pred.argmax(1) == y).type(torch.float).sum().item()
                
                #calculate batch accuracy
                accuracy = correct / x.size(0) #divided by length x because the last batch will be different then batch size
                
                #during an epoch printed the batch accuracy
                tepoch.set_postfix(loss=loss.item(), accuracy=100.0 * accuracy)
                
            
            #calculate the average loss
            train_losses.append(trainLoss/count)
            
            #calculate accuracy
            train_acc.append(trainCorrect/len(train_loader.dataset))
            print("Train Accuracy:",trainCorrect/len(train_loader.dataset))
            
            
        valLoss = 0
        valCorrect = 0
        
        with torch.no_grad():
            
            # set the model for evaluation
            model.eval() 
            
            # loop over the test set
            count=0
            for (x, y) in valid_loader:
                count+=1
                (x, y) = (x.to(device), y.to(device))
                
                #forward step
                pred = model(x)
                
                #calculate loss
                loss = lossFn(pred, y) 
                valLoss += loss
                
                #calculate total number of correct predictions
                valCorrect += (pred.argmax(1) == y).type(torch.float).sum().item()
                correct = (pred.argmax(1) == y).type(torch.float).sum().item()
                accuracy = correct / x.size(0)
                
            val_losses.append(valLoss/count)
            val_acc.append(valCorrect/len(valid_loader.dataset))
            print("Validation Accuracy",valCorrect/len(valid_loader.dataset))
        
        #check early stopping every 1 epochs
        if(early_stop and (e+1)%3==0 ):
            print("Early stopping checking")
            print("Validation Loss:",(valLoss/count).item())
            print("Training Loss:",(train_losses[e]).item())
            if(estopper.early_stop(valLoss/count,train_losses[e])):
                break
        print("{}. epoch is finished!".format(e+1))
        print("-"*50)
        
        
    return model,train_losses, val_losses, train_acc, val_acc

#Plot losses and accuracies of each epoch for compare epoch
def plot_epoch_metric(train_loss, val_loss, train_acc, val_acc):
    x_arr = np.arange(len(train_loss)) + 1
    fig = plt.figure(figsize=(15, 6))
    ax = fig.add_subplot(1, 2, 1)
    
    train_loss_arr=[i.cpu().detach().numpy() for i in train_loss]
    val_loss_arr=[i.cpu().detach().numpy() for i in val_loss]
    
    ax.plot(x_arr, train_loss_arr, '-*', label='Train loss')
    ax.plot(x_arr, val_loss_arr, '--v', label='Validation loss')
    ax.set_title("Loss",size=17)
    ax.legend(fontsize=13)
    
    train_acc_arr=[i for i in train_acc]
    val_acc_arr=[i for i in val_acc]
    
    ax = fig.add_subplot(1, 2, 2)
    ax.plot(x_arr, train_acc_arr, '-*', label='Train accuracy')
    ax.plot(x_arr, val_acc_arr, '--v',label='Validation accuracy')
    ax.set_title("Accuracy",size=17)
    ax.legend(fontsize=13)
    
    ax.set_xlabel('Epoch', size=13)
    ax.set_ylabel('Accuracy', size=13)
    plt.show()

#evaluate test dataset with confusion matrix, accuracy, precision, recall and f1-score
def evaluate_test(model,test_dl,loss_fn,labels):
    if torch.cuda.is_available():
        model.cuda()
    
    ground_truth=[]
    predict=[]
    
    with torch.no_grad():
        for i, (inputs, classes) in enumerate(test_dl):
            inputs = inputs.to(device)
            classes = classes.to(device)
            outputs = model(inputs)
            
            #get predict classes and corresponding ground truths
            _, preds = torch.max(outputs, 1)
            ground_truth.extend(classes.view(-1).tolist())
            predict.extend(preds.view(-1).tolist())
    
    #calculate accuracies, recalls, precisions and f1-score. Print confusuion matrix.
    conf_matrix = confusion_matrix(y_true=ground_truth, y_pred=predict)
    print('Confusion Matrix:')
    print()
    print(conf_matrix)
    print()
    print(classification_report(ground_truth, predict, digits=3))

"""# ALL weights include in VGG-19

> **WITHOUT EARLY STOPPING**
"""

model=models.vgg19(pretrained=True)

#activate layers
layers=[]
for param in model.parameters():
    layers.append(param)
for layer in layers:
    layer.requires_grad=True
for param in model.parameters():
    print(param.requires_grad)

#information of model parameters
print(model.named_parameters)

#change length of output 
numFeature = model.classifier[-1].in_features
model.classifier[-1] = nn.Linear(numFeature, numclass)
model.classifier[-1]

# adding loss function and optimizer to the model
loss_fun=nn.CrossEntropyLoss()
optimizer=torch.optim.Adam(model.parameters(),lr=0.001)

#decrease learning rate factor of 0.1 every 5 step 
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)

#Without Early stopping
num_epochs=15
model,train_losses, val_losses, train_acc, val_acc=train(model,num_epochs,train_dl,val_dl,loss_fun,optimizer,scheduler,BATCH_SIZE)

#save model
torch.save(model.state_dict(),'weights1.pt')

"""Our model approached 100% accuracy, but it started to become overfit at 90% accuracy. 

Loss showed overfit after 0.4 loss.

In other words, there is an overfit condition observed after the 6th epoch
"""

plot_epoch_metric(train_losses, val_losses, train_acc, val_acc)

"""The model performed best on the 7th class. but overall it achieved precision recall f1 score and accuracy over 90%. This shows that overfitting is still not much.

The **best** class is **carrot**. F1 score -> 0.987

The **worst** class is **cabbage**. F1 score -> 0.888

The accuracy is lower than train accuracy and same as validation accuracy.
"""

evaluate_test(model,test_dl,loss_fun,class_names)

""">**WITH EARLY STOPPING**"""

model=models.vgg19(pretrained=True)

#activate layers 
layers=[]
for param in model.parameters():
    layers.append(param)
for layer in layers:
    layer.requires_grad=True
for param in model.parameters():
    print(param.requires_grad)

#change length of output 
numFeature = model.classifier[-1].in_features
model.classifier[-1] = nn.Linear(numFeature, numclass)
model.classifier[-1]

# adding loss function and optimizer to the model
loss_fun=nn.CrossEntropyLoss()
optimizer=torch.optim.Adam(model.parameters(),lr=0.001)

#decrease learning rate factor of 0.1 every 5 step 
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)

#With Early stopping
num_epochs=15
model,train_losses, val_losses, train_acc, val_acc=train(model,num_epochs,train_dl,val_dl,loss_fun,optimizer,scheduler,BATCH_SIZE,early_stop=True)

#save model
torch.save(model.state_dict(),'weights2.pt')

"""Overfitting was observed after the 7th epoch. Our Early stopping system checks for overfitting every 3 epochs. Here, in the 9th epoch, education was stopped.

The reason for the difference in the loss and accuracy values compared to the previous model is completely related to the different mixing of the train dataset.
"""

plot_epoch_metric(train_losses, val_losses, train_acc, val_acc)

"""The model performed best on the 7th class. but overall it achieved precision recall f1 score and accuracy over 93%. This shows that overfitting is still not much.

The **best** class is **carrot**. F1 score -> 0.993

The **worst** class is **pumpkin**. F1 score -> 0.912

In here accuray is higher than validation accuracy however lower than training accuracy. If we compare this accuracy with "Without early stopping" model accuracy this one is better.
"""

evaluate_test(model,test_dl,loss_fun,class_names)

"""#  Only fully connected of VGG-19

> WITHOUT EARLY STOPPING
"""

model=models.vgg19(pretrained=True)

#
layers=[]
for param in model.parameters():
    layers.append(param)
for layer in layers:
    layer.requires_grad=False
for param in model.parameters():
    print(param.requires_grad)

#change length of output 
numFeature = model.classifier[-1].in_features
model.classifier[-1] = nn.Linear(numFeature, numclass)
model.classifier[-1]

model.classifier #FC

# adding loss function and optimizer to the model
loss_fun=nn.CrossEntropyLoss()
optimizer=torch.optim.Adam(model.parameters(),lr=0.001)

# Decrease learning rate factor of 0.1 every 5 step 
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)

num_epochs=15
model,train_losses, val_losses, train_acc, val_acc=train(model,num_epochs,train_dl,val_dl,loss_fun,optimizer,scheduler,BATCH_SIZE)

"""Loss and accuracy are very high. In addition, when we compare the validation accuracy with the Trainin accuracy, there is no overfitting situation. In addition, these models, which include only fully connected, worked better than our first two models, that is, trainings involving all layers.  """

plot_epoch_metric(train_losses, val_losses, train_acc, val_acc)

"""Looking at the test evaluation, it achieved better accuracy than Train and Validation accuracy. So our model works really well. We get almost 100% accuracy.
Besides these, there are values ​​with **f1 score of 1**. They were predicted 100% correctly on the test set.

These:
**Bottle_Gourd, Carrot, Potato, Radish** are classes.

The worst are **Brinjal and Papaya** classes with an **F1 score of 0.99**. But of course, it would be very wrong to call the value of 99% bad. The bad among the good.

"""

evaluate_test(model,test_dl,loss_fun,class_names)

torch.save(model.state_dict(),'weights3.pt')

"""> WITH EARLY STOPPING"""

model=models.vgg19(pretrained=True)

#drop layers other then fully connected
layers=[]
for param in model.parameters():
    layers.append(param)
for layer in layers:
    layer.requires_grad=False
for param in model.parameters():
    print(param.requires_grad)

#change length of output 
numFeature = model.classifier[-1].in_features
model.classifier[-1] = nn.Linear(numFeature, numclass)
model.classifier[-1]

model.classifier #FC

# adding loss function and optimizer to the model
loss_fun=nn.CrossEntropyLoss()
optimizer=torch.optim.Adam(model.parameters(),lr=0.001)

# Decrease learning rate factor of 0.1 every 5 step 
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)

num_epochs=15
model,train_losses, val_losses, train_acc, val_acc=train(model,num_epochs,train_dl,val_dl,loss_fun,optimizer,scheduler,BATCH_SIZE,early_stop=True)

torch.save(model.state_dict(),'weights4.pt')

"""This model is the same as the previous model. Compared to the previous model, we only added early stopping here, but since the model did not need early stopping, it completed 15 epochs and got a similar output. Although there is a difference, this is due to the shuffle of the train and validation dataset."""

plot_epoch_metric(train_losses, val_losses, train_acc, val_acc)

"""The comment to be made here is very similar to the previous one. Again, the model's accuracy value is better than train and validation. **Those with an F1 score of 1 are still the same classes.**

These:

**Bottle_Gourd, Carrot, Potato, Radish **are classes.

In the bad ones,** Brinjalin** f1 score decreased very little.** Papaya'**s remained the same.
"""

evaluate_test(model,test_dl,loss_fun,class_names)

"""To compare the results of part1 with two hidden layers here, we have chosen the best accuracy in part1.


MLP model metrics:


```
              precision    recall  f1-score   support

           0      0.049     0.035     0.041       200
           1      0.015     0.015     0.015       200
           2      0.044     0.050     0.047       200
           3      0.030     0.040     0.034       200
           4      0.053     0.055     0.054       200
           5      0.033     0.050     0.040       200
           6      0.006     0.005     0.005       200
           7      0.022     0.015     0.018       200
           8      0.032     0.035     0.033       200
           9      0.030     0.045     0.036       200
          10      0.054     0.025     0.034       200
          11      0.358     0.680     0.469       200
          12      0.037     0.015     0.021       200
          13      0.024     0.020     0.022       200
          14      0.000     0.000     0.000       200

    accuracy                          0.072      3000
   macro avg      0.052     0.072     0.058      3000
weighted avg      0.052     0.072     0.058      3000

```

The confusion matrix seen above is the output of the model trained with 0.02 learning rate 16 batch size tanh+tanh activation functions. The result from all the model trained in VGG-19 are better than this one. This is because VGG-19 is a pretrained model. Also, our mlp model didn't perform well on validation and test data.
"""





