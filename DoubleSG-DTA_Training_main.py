'''
Author: Yongtao Qian
Time: 2023-2-5
model: DoubleSG-DTA
'''

import numpy as np
import pandas as pd
import sys, os
from random import shuffle
import torch
import torch.nn as nn
from models.ginconv import GINConvNet
from utils import *


# training function at each epoch
def train(model, device, train_loader, optimizer, epoch):
    print('Training on {} samples...'.format(len(train_loader.dataset)))
    model.train()
    for batch_idx, data in enumerate(train_loader):
        data = data.to(device)
        optimizer.zero_grad()
        output = model(data)
        loss = loss_fn(output, data.y.view(-1, 1).float().to(device))
        loss.backward()
        optimizer.step()
        if batch_idx % LOG_INTERVAL == 0:
            print('Train epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(epoch,
                                                                           batch_idx * len(data.x),
                                                                           len(train_loader.dataset),
                                                                           100. * batch_idx / len(train_loader),
                                                                           loss.item()))


def predicting(model, device, loader):
    model.eval()
    total_preds = torch.Tensor()
    total_labels = torch.Tensor()
    print('Make prediction for {} samples...'.format(len(loader.dataset)))
    with torch.no_grad():
        for data in loader:
            data = data.to(device)
            output = model(data)
            total_preds = torch.cat((total_preds, output.cpu()), 0)
            total_labels = torch.cat((total_labels, data.y.view(-1, 1).cpu()), 0)
    return total_labels.numpy().flatten(), total_preds.numpy().flatten()

'''
Select one of the data sets for each training.
0-->Davis
1-->KIBA
2-->bindingdb
'''
datasets = [['davis', 'kiba', 'bindingdb'][int(sys.argv[1])]]

# Our models are stored in the models folder, named Ginconv
modeling = [GINConvNet]
model_st = modeling.__name__

# You can have multiple GPUs running at the same time or a single GPU, please select the number of the free GPU
cuda_name = "cuda:0"
if len(sys.argv) > 3:
    cuda_name = "cuda:" + str(int(sys.argv[2]))
print('cuda_name:', cuda_name)

TRAIN_BATCH_SIZE = 1024
TEST_BATCH_SIZE = 1024
LR = 0.0001
LOG_INTERVAL = 20
NUM_EPOCHS = 600

print('Learning rate: ', LR)
print('Epochs: ', NUM_EPOCHS)

# Main program: iterate over different datasets
for dataset in datasets:
    print('\nrunning on ', model_st + '_' + dataset)
    processed_data_file_train = 'autodl-tmp/DoubleSG-DTA/data/processed/' + dataset + '_train.pt'
    processed_data_file_test = 'autodl-tmp/DoubleSG-DTA/data/processed/' + dataset + '_test.pt'
    if ((not os.path.isfile(processed_data_file_train)) or (not os.path.isfile(processed_data_file_test))):
        print('please run create_data.py to prepare data in pytorch format!')
    else:
        train_data = TestbedDataset(root='autodl-tmp/DoubleSG-DTA/data', dataset=dataset + '_train')
        test_data = TestbedDataset(root='autodl-tmp/DoubleSG-DTA/data', dataset=dataset + '_test')

        # make data PyTorch mini-batch processing ready
        train_loader = DataLoader(train_data, batch_size=TRAIN_BATCH_SIZE, shuffle=True, num_workers=8,pin_memory=True)
        test_loader = DataLoader(test_data, batch_size=TEST_BATCH_SIZE, shuffle=False, num_workers=8,pin_memory=True)

        # training the model
        device = torch.device(cuda_name if torch.cuda.is_available() else "cpu")
        model = modeling().to(device)
        loss_fn = nn.MSELoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=LR)
        best_mse = 1000
        best_ci = 0
        best_epoch = -1
        model_file_name = 'model_gin_' + model_st + '_' + dataset + '.model'
        result_file_name = 'result_gin7_' + model_st + '_' + dataset + '.csv'
        test_result_file = 'autodl-tmp/DoubleSG-DTA/' + 'test_total_result_gin_' + model_st + '_' + dataset + '.csv'
        
        
#         path='model_gin_GINConvNet_bindingdb.model'
#         model.load_state_dict(torch.load(path))
        
        
        # Start training 600 epochs
        for epoch in range(NUM_EPOCHS):
            train(model, device, train_loader, optimizer, epoch + 1)
            G, P = predicting(model, device, test_loader)
            ret = [epoch, rmse(G, P), mse(G, P), pearson(G, P), spearman(G, P), ci(G, P), get_rm2(G, P)]
            
            # Record the test set performance results for each round, in order，epoch, rmse(G, P), mse(G, P), pearson(G, P), spearman(G, P), ci(G, P), get_rm2(G, P)
            with open(test_result_file, 'a') as f:
                f.write(','.join(map(str, ret)) + '\n')
            # We train with the objective of minimising MSE
            if ret[2] < best_mse:
                torch.save(model.state_dict(), model_file_name)
                with open(result_file_name, 'w') as f:
                    f.write(','.join(map(str, ret)))
                best_epoch = epoch + 1
                best_mse = ret[2]
                best_ci = ret[-2]
                print('rmse improved at epoch ', best_epoch, '; best_mse,best_ci:', best_mse, best_ci, model_st,
                      dataset)
            else:
                print(ret[2], 'No improvement since epoch ', best_epoch, '; best_mse,best_ci:', best_mse, best_ci,
                      model_st, dataset)
