# -*- coding: utf-8 -*-
"""Project_ReduBias_training.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1_NTNGtdTE9JS1W1f5KHPOc88MZYmL-v5

# Mitigating Bias in Language Models Using DRL
Rameez Qureshi | University of Lorraine | INRIA Rennes

The architecture can be divided into 5 major parts:



Completed
1.   Combining flipped and negated templates together for each template.
2.   Functions to predicts the answer of 4 variants.
3.   Function to calculate bias for each step.
4.   Function for policy update step.
5.   Training Loop.
6. Update the probability calculation function.
7. Add a normalization function
8. Define batch Manhattan
9. Retain the gradient graph of reward function

Remaining

"""
import sys
import argparse
import os
import torch
import numpy as np
from torch.autograd import Variable
from torch import nn
from torch import cuda

import torch.nn.functional as F
from torch import FloatTensor


import json
from utils.holder import *
from utils.extract import get_tokenizer, tokenize_underspecified_input
from transformers import *
import math
from redubias.calc_bias import Dataset, calculate_reward, calculate_batch_manhattan, collate_fn,unqover_reward
# from redubias.predict_topk import predict_answers
from redubias.predict_topk import predict_answers
from model_roberta import CustomroBERTaModel
import _pickle as pickle
from time import process_time
import random
# from templates.lists import Lists
#%%
gpuid = -1
# if gpuid != -1:
#     torch.cuda.set_device(gpuid)
#     torch.cuda.manual_seed_all(1)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

#%%

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--epochs', type=int, default=1)
    parser.add_argument('--device', type=int, default=0,
                    help='select GPU')
    parser.add_argument('--mini_batch_size', type=int, default=20, help="Size of batch per update")
    parser.add_argument('--batch_size', type=int, default=70, help = "Samples per Template")
    parser.add_argument('--lr', type=float, default=5e-5, help = "Learning Rate")
    parser.add_argument('--topk', type=int, default=10, help = "TopK")
    parser.add_argument('--output', type=str, default="new_model", help = "Name of the model")
    parser.add_argument('--ppdata', type=str, default="", help = "Path of the preprocessed data")
    parser.add_argument('--use_he_she', help="Whether to account for lm predictions on he/she", type=int, default=0)
    args = parser.parse_args()
    torch.cuda.set_device(args.device)
    ppdata_path = args.ppdata
## Loading Pre-processed Data

    # lists = Lists("word_lists", None)
    # args.female, args.male = load_gender_names(lists)

    from transformers import set_seed

    set_seed(0)

    with open(ppdata_path, 'rb') as file:
        pp_data = pickle.load(file)

    keys = list(pp_data.keys())#[:10000]#HACK
    values = list(pp_data.values())#[:10000]#HACK
    values = [pp_data[k] for k in keys]

    batch_size = args.batch_size
    training_values = Dataset(values)
    # random_sampler = torch.utils.data.RandomSampler(training_values)
    training_generator = torch.utils.data.DataLoader(training_values, batch_size=batch_size, collate_fn=collate_fn, num_workers=2)
    
    #######VARIABLES########
    mini_batch_size = args.mini_batch_size
    batch_size = args.batch_size
    num_epochs = args.epochs
    lr = args.lr
    topk = args.topk
    name = args.output
    """Defining Model"""
    print("Defining Model", flush=True)
    #NOTE: Insert the name of the model here
    transformer_type = "bert-base-uncased"
    model = CustomroBERTaModel(topk, batch_size).to(device)

    for layer_name, param in model.named_parameters():
        if 'bert' in layer_name:
            param.requires_grad = False
    print("Loading Dataset", flush=True)
    training_values = Dataset(values)
    # random_sampler = torch.utils.data.RandomSampler(training_values, replacement=False, num_samples=10000)
    # training_generator = torch.utils.data.DataLoader(training_values, batch_size=batch_size, collate_fn=collate_fn)

    learning_rate = lr
    print("Number of Samples: ", len(training_generator), flush=True)
    print(args)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    num_training_steps = num_epochs * len(training_generator)
    print("Number of training steps : ",num_training_steps, flush=True)
    step = 0
    model.train()
    # loss_list = []
    rewards = []
    print("Starting training")
    start = process_time()
    cp_path = 'data/logs/training_logs/'+name + '.pt'
    print('Name:', name)
    for epoch in range(num_epochs):
        # Training
        for local_batch in training_generator:
            with torch.cuda.device(0):
            # Transfer to GPU
                loss, reward = calculate_reward(args, local_batch, mini_batch_size, topk, model.tokenizer, model)
                # Print only at 1000 steps
                if step % 100 == 0:
                    print("Step ", step, "| Loss:  ", loss.item(), "| Reward: ", reward, flush=True)

                if not torch.isnan(loss):
                    loss.backward()

                optimizer.step()

                optimizer.zero_grad()

                # loss_list.append(loss.detach())
                rewards.append(reward)

                step += 1

    stop = process_time()
    print("time elapsed: ", stop - start)
    #Save model
    model_path = 'saved_models/'+name + '.pt'
    torch.save(model, 'saved_models/'+name)

    print("Arguments: ", args)
    # torch.save({'epoch': epoch, 'model_state_dict':model.state_dict(), 'optimizer.state_dict': optimizer.state_dict(), 'loss': loss}, cp_path)

    # with open("saved_models/"+name+".txt", "wb") as fp:   #Pickling
    #     pickle.dump(rewards, fp)
    # print('Saved model at', model_path)

if __name__ == '__main__':
    main()