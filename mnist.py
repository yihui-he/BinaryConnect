# Copyright 2015 Matthieu Courbariaux, Zhouhan Lin

"""
This file is adapted from BinaryConnect:

    https://github.com/MatthieuCourbariaux/BinaryConnect

Running this script should reproduce the results of a feed forward net trained
on MNIST.

To train a vanilla feed forward net with ordinary backprop:
   1. type "git checkout fullresolution" to switch to the "fullresolution" branch
   2. execute "python mnist.py"

To train a feed forward net with Binary Connect + quantized backprop:
   1. type "git checkout binary" to switch to the "binary" branch
   2. execute "python mnist.py"

To train a feed forward net with Ternary Connect + quantized backprop:
   1. type "git checkout ternary" to switch to the "ternary" branch
   2. execute "python mnist.py"

"""

import gzip
import cPickle
import numpy as np
import os
import os.path
import sys
import time

from trainer import Trainer
from model import Network
from layer import linear_layer, ReLU_layer  

from pylearn2.datasets.mnist import MNIST
from pylearn2.utils import serial
       

if __name__ == "__main__":
    
    rng = np.random.RandomState(1234)
    train_set_size = 50000
    
    # data augmentation
    zero_pad = 0
    affine_transform_a = 0
    affine_transform_b = 0
    horizontal_flip = False
    
    # batch
    # keep a multiple a factor of 10000 if possible
    # 10000 = (2*5)^4
    batch_size = 200
    number_of_batches_on_gpu = train_set_size/batch_size
    BN = True
    BN_epsilon=1e-4 # for numerical stability
    BN_fast_eval= True
    dropout_input = 1.
    dropout_hidden = 1.
    shuffle_examples = True
    shuffle_batches = False

    # Termination criteria
    n_epoch = 1000
    monitor_step = 2
    
    # LR 
    LR = .3
    LR_fin = .01
    LR_decay = (LR_fin/LR)**(1./n_epoch)    
    M= 0.
    
    # architecture
    n_inputs = 784
    n_units = 1024
    n_classes = 10
    n_hidden_layer = 3
    
    # BinaryConnect
    BinaryConnect = True
    stochastic = True
    
    # Old hyperparameters
    binary_training=False 
    stochastic_training=False
    binary_test=False
    stochastic_test=False
    if BinaryConnect == True:
        binary_training=True      
        if stochastic == True:   
            stochastic_training=True  
        else:
            binary_test=True
    
    print 'Loading the dataset' 
    
    train_set = MNIST(which_set= 'train', start=0, stop = train_set_size, center = True)
    valid_set = MNIST(which_set= 'train', start=50000, stop = 60000, center = True)
    test_set = MNIST(which_set= 'test', center = True)
    
    # bc01 format
    train_set.X = train_set.X.reshape(train_set_size,1,28,28)
    valid_set.X = valid_set.X.reshape(10000,1,28,28)
    test_set.X = test_set.X.reshape(10000,1,28,28)
    
    # flatten targets
    train_set.y = np.hstack(train_set.y)
    valid_set.y = np.hstack(valid_set.y)
    test_set.y = np.hstack(test_set.y)
    
    # Onehot the targets
    train_set.y = np.float32(np.eye(10)[train_set.y])    
    valid_set.y = np.float32(np.eye(10)[valid_set.y])
    test_set.y = np.float32(np.eye(10)[test_set.y])
    
    # for hinge loss
    train_set.y = 2* train_set.y - 1.
    valid_set.y = 2* valid_set.y - 1.
    test_set.y = 2* test_set.y - 1.
    
    print 'Creating the model'
    
    class PI_MNIST_model(Network):

        def __init__(self, rng):
            
            Network.__init__(self, n_hidden_layer = n_hidden_layer, BN = BN)
            
            print "    Fully connected layer 1:"
            self.layer.append(ReLU_layer(rng = rng, n_inputs = n_inputs, n_units = n_units,
                BN = BN, BN_epsilon=BN_epsilon, dropout=dropout_input,
                binary_training=binary_training, stochastic_training=stochastic_training,
                binary_test=binary_test, stochastic_test=stochastic_test))
            
            for k in range(n_hidden_layer-1):
                
                print "    Fully connected layer "+ str(k) +":"
                self.layer.append(ReLU_layer(rng = rng, n_inputs = n_units, n_units = n_units,
                    BN = BN, BN_epsilon=BN_epsilon, dropout=dropout_hidden, 
                    binary_training=binary_training, stochastic_training=stochastic_training,
                    binary_test=binary_test, stochastic_test=stochastic_test))
                
            print "    L2 SVM layer:"
            self.layer.append(linear_layer(rng = rng, n_inputs = n_units, n_units = n_classes,
                BN = BN, BN_epsilon=BN_epsilon, dropout=dropout_hidden, 
                binary_training=binary_training, stochastic_training=stochastic_training,
                binary_test=binary_test, stochastic_test=stochastic_test))
    
    model = PI_MNIST_model(rng = rng)
    
    print 'Creating the trainer'
    
    trainer = Trainer(rng = rng,
        train_set = train_set, valid_set = valid_set, test_set = test_set,
        model = model, load_path = None, save_path = None,
        zero_pad=zero_pad,
        affine_transform_a=affine_transform_a, # a is (more or less) the rotations
        affine_transform_b=affine_transform_b, # b is the translations
        horizontal_flip=horizontal_flip,
        LR = LR, LR_decay = LR_decay, LR_fin = LR_fin,
        M = M,
        BN = BN, BN_fast_eval=BN_fast_eval,
        batch_size = batch_size, number_of_batches_on_gpu = number_of_batches_on_gpu,
        n_epoch = n_epoch, monitor_step = monitor_step,
        shuffle_batches = shuffle_batches, shuffle_examples = shuffle_examples)
    
    print 'Building'
    
    trainer.build()
    
    print 'Training'
    
    start_time = time.clock()  
    trainer.train()
    end_time = time.clock()
    print 'The training took %i seconds'%(end_time - start_time)
    
    print 'Display weights'
    
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    from filter_plot import tile_raster_images
    
    W = np.transpose(model.layer[0].W.get_value())
    W = tile_raster_images(W,(28,28),(4,4),(2, 2))
    plt.imshow(W, cmap = cm.Greys_r)
    plt.savefig(core_path + '_features.png')
