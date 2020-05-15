
import os

import numpy as np
import pandas as pd

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.cm as cm


import pandas as pd
import numpy as np
import scipy as sp

import logomaker

#define functions
def seq2mat(seq, seq_dict):
    '''Convert a sequence into a matrix representation of shape (4,L)'''
    mat = sp.zeros((len(seq_dict),len(seq)),dtype=int)
    for i,bp in enumerate(seq):
        mat[seq_dict[bp],i] = 1
    return mat


def choose_dict(dicttype,modeltype='MAT'):
    '''Creates a necessary tool to convert from bp to an index'''
    if dicttype == 'dna':
        seq_dict = {'A':0,'C':1,'G':2,'T':3}
        inv_dict = {0:'A',1:'C',2:'G',3:'T'}
    elif dicttype == 'rna':
        seq_dict = {'A':0,'C':1,'G':2,'U':3}
        inv_dict = {0:'A',1:'C',2:'G',3:'U'}
    elif dicttype == 'protein':
        seq_dict = {
            '*':0,'A':1,'C':2,'D':3,'E':4,'F':5,'G':6,'H':7,'I':8,'K':9,'L':10,
            'M':11,'N':12,'P':13,'Q':14,'R':15,'S':16,'T':17,'V':18,'W':19,'Y':20}
        inv_dict = {v:k for k,v in seq_dict.items()}
    else:
        raise SortSeqError('Unkonwn dicttype: %s'%dicttype)

    if modeltype == 'NBR' or modeltype == 'PAIR':
        seq_dict = {
            ''.join([inv_dict[i],inv_dict[z]]):i*len(seq_dict)+z
            for i in range(len(seq_dict)) for z in range(len(seq_dict))}
        inv_dict = {seq_dict[i]:i for i in seq_dict.keys()}
    return seq_dict,inv_dict


def sliding_window(y,windowsize=3):
    """Average information values with neighbors."""
    out_vec = np.zeros((len(y)-windowsize))
    for i in range(len(y)-windowsize):
        out_vec[i] = np.sum(y[i:i+windowsize])/windowsize
    return out_vec


def calcinfo(prob, bg):
    '''Calculate mutual information from a probability matrix.'''
    prob = prob + 1e-7
    bg = bg + 1e-7
    return np.sum(prob*np.log2(prob/bg))


def convert_to_df(em):
    outdf = pd.DataFrame()
    outdf['val_mut'] = em
    outdf['val_wt'] = 0
    outdf['pos'] = range(len(outdf.index))
    outdf = outdf[['pos','val_wt','val_mut']]
    return outdf


def effect_df_to_prob_df(effect_df, bg_df, beta):
    prob_df = effect_df.copy()
    vals = effect_df.values
    vals -= vals.min(axis=1)[:,np.newaxis]
    weights = np.exp(-beta*vals)*bg_df.values
    prob_df.loc[:,:] = weights/weights.sum(axis=1)[:,np.newaxis]
    return prob_df

#determine the relative probabilities of being mutated/being wt. In reality this
#is about 10 percent towards being mutated. However, to control for possible
#differing mutation rates, we will just arbitrarily set the ratio to be 50/50

def footprint(inarr, for_clip=False, seqlength=160, for_invert=False):
    """
    """
    windowsize=3

    background_array =pd.DataFrame([[.5,.5]])

    energy_df = convert_to_df(inarr)

    val_cols = ['val_wt','val_mut']
    energyarr = np.array(energy_df[val_cols]).T

    seq_dict,inv_dict = choose_dict('dna')

    #Create a matrix and use it to see if we need to invert all matrix values. We
    #will also use this to set color type of plot.
    y_sub = np.array(energyarr[1,:])

    if y_sub.sum() > 0:
        y_sub = y_sub*-1

    if for_invert == 'invert':
        y_sub = y_sub*-1
        
    y_sub_smoothed = sliding_window(y_sub)
    abs_sub = np.abs(y_sub_smoothed)
    maxval = np.max(abs_sub)
    y_sub_normed = y_sub_smoothed/maxval/2 + 0.5
    colorinputs = np.zeros((seqlength))
    for i in range(seqlength-windowsize):
        if y_sub_smoothed[i] < 0:
            colorinputs[i] = 0.0
        else:
            colorinputs[i] = 1.0

    if for_clip == 'clip':
        total_length = len(energy_df.index)
        energy_df = energy_df.loc[:total_length-21,:]

    energy_df = energy_df[['val_wt','val_mut']]

    energy_df_scaled = energy_df

    background_df = pd.DataFrame(np.tile(background_array,
                        (len(energy_df_scaled), 1)), columns=['val_wt','val_mut'])
    emat_min = -2
    emat_max = 2
    mid_val=0

    #calculate the probability matrices
    mutlogo = effect_df_to_prob_df(energy_df_scaled,background_df,1)
    mut2logo = effect_df_to_prob_df(-1*energy_df_scaled,background_df,1)
    mutarr = np.array(mutlogo).T
    mut2arr = np.array(mut2logo).T


    mutinfo = np.zeros(seqlength)
    mutbgprob = np.zeros(2)
    for i in range(seqlength):
        mutbgprob[0] = .5
        mutbgprob[1] = 1-mutbgprob[0]
        if y_sub[i] > 0:
            mutinfo[i] = calcinfo(mutarr[:,i],mutbgprob)
        else:
            mutinfo[i] = -1*calcinfo(mut2arr[:,i],mutbgprob)
            
    tempoutdf = pd.DataFrame()
    tempoutdf['pos'] = range(1,seqlength-windowsize+1)
    tempoutdf['info'] = sliding_window(mutinfo)
    smoothinfo = sliding_window(np.abs(mutinfo),windowsize=windowsize)
    shiftcolors = plt.cm.bwr(colorinputs)
    return np.abs(smoothinfo), shiftcolors



def get_info(df, gc=.508):
    '''Find the total information content of a binding site.'''
    

    background_array = np.array([(1 - gc) / 2, gc / 2, gc / 2, (1 - gc) / 2])
    
    #add in small value to make sure no probabilities are exactly zero.
    df = df + 1e-9
    
    return np.sum(df.values * np.log2(df.values/background_array))


def get_beta_for_effect_df(
    effect_df,
    target_info,
    min_beta=.001,
    max_beta=100,
    num_betas=1000):
    '''Find the appropriate scaling factor for displaying sequence
    logos. '''
    betas = np.exp(np.linspace(np.log(min_beta),np.log(max_beta),num_betas))
    infos = np.zeros(len(betas))
    for i, beta in enumerate(betas):
        prob_df = logomaker.transform_matrix(df=beta*effect_df,from_type='weight',to_type='probability')
        infos[i] = get_info(prob_df)
    i = np.argmin(np.abs(infos-target_info))
    beta = betas[i]
    return beta