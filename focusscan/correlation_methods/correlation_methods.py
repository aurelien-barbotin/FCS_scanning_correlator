import numpy as np
#import fib4
import time
import _thread

"""FCS Bulk Correlation Software

    Copyright (C) 2015  Dominic Waithe

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""


def tttr2xfcs (y,num,NcascStart,NcascEnd, Nsub):
    
    """autocorr, autotime = tttr2xfcs(y,num,10,20)
     Translation into python of:
     Fast calculation of fluorescence correlation data with asynchronous time-correlated single-photon counting.
     Michael Wahl, Ingo Gregor, Matthias Patting, Jorg Enderlein

     This algorithm is most appropriate to use with time-tag data, whereby the photons are recorded individually as they arrive.
     The arrival times are correlated rather than binned intensities (though some binning is performed at later cycles).

     for intensity data which is recorded at regular intervals use a high-peforming correlation such as multipletau:
     (https://github.com/FCS-analysis/multipletau_)

     or a basic numpy version which can be found amongst others here:
     https://github.com/dwaithe/generalMacros/blob/master/diffusion%20simulations%20/Correlate%20Comparison.ipynb

    
    --- inputs --- 
    
    y:      An array of the photon arrival times for both channels.
    num:    This a 2D boolean array of the photons in each channel. 
            A '1' represents a photon at each corresponding time (row) in y in each channel (col)
    
    Ncasc in general refers to the number of logarithmic ranges to calculate the correaltion function.
    NcascStart: This is a feature I added whereby you can start the correlation at a later stage.
    NcasEnd:    This is the last level of correlation
    
    Nsub:   This is the number of sub-levels correlated at each casc level.
            You can think of this as the level of detail. The higher the value the more noisey

    --- outputs ---
    auto:       This is the un-normalised  auto and cross-correlation function output.
                auto[:,0,0] = autocorrelation channel 0
                auto[:,1,1] = autocorrelation channel 1
                auto[:,1,0] = crosscorrelation channel 10
                auto[:,0,1] = crosscorrelation channel 01
    autotime: This is the associated tau time range.  


     """
 
    dt = np.max(y)-np.min(y)
    y = np.round(y[:],0)
    numshape = num.shape[0]
     
    autotime = np.zeros(((NcascEnd+1)*(Nsub+1),1));
    auto = np.zeros(((NcascEnd+1)*(Nsub+1), num.shape[1], num.shape[1])).astype(np.float64)
    shift = float(0)
    delta = float(1)
    
    
    
    for j in range(0,NcascEnd):
        
        #Finds the unique photon times and their indices. The division of 'y' by '2' each cycle makes this more likely.
        
        y,k1 = np.unique(y,1)
        k1shape = k1.shape[0]
        
        #Sums up the photon times in each bin.
        cs =np.cumsum(num,0).T
        
        #Prepares difference array so starts with zero.
        diffArr1 = np.zeros(( k1shape+1));
        diffArr2 = np.zeros(( k1shape+1));
        
        #Takes the cumulative sum of the unique photon arrivals
        diffArr1[1:] = cs[0,k1].reshape(-1)
        diffArr2[1:] = cs[1,k1].reshape(-1)
        
        #del k1
        #del cs
        num =np.zeros((y.shape[0],2))
        

        
        #Finds the total photons in each bin. and represents as count.
        #This is achieved because we have the indices of each unique time photon and cumulative total at each point.
        num[:,0] = np.diff(diffArr1)
        num[:,1] = np.diff(diffArr2)
        #diffArr1 = [];
        #diffArr2 = [];
        
        for k in range(0,Nsub):
            shift = shift + delta
            lag = np.round(shift/delta,0)
    
            
            #Allows the script to be sped up.
            if j >= NcascStart:
                

                #Old method
                i1= np.in1d(y,y+lag,assume_unique=True)
                i2= np.in1d(y+lag,y,assume_unique=True)
                
                #New method, cython
                # i1,i2 = fib4.dividAndConquer(y, y+lag,y.shape[0]+1)


                #If the weights (num) are one as in the first Ncasc round, then the correlation is equal to np.sum(i1)
                
                i1 = np.where(i1.astype(np.bool))[0]
                i2 = np.where(i2.astype(np.bool))[0]

                #Now we want to weight each photon corectly.
                #Faster dot product method, faster than converting to matrix.
                
                if i1.size and i2.size:
                    jin = np.dot((num[i1,:]).T,num[i2,:])/delta
                       
                    auto[(k+(j)*Nsub),:,:] = jin
            
            autotime[k+(j)*Nsub] =shift
        
        #Equivalent to matlab round when numbers are %.5
        y = np.ceil(np.array(0.5*y))
        delta = 2*delta
    
    for j in range(0, auto.shape[0]):
        auto[j,:,:] = auto[j,:,:]*dt/(dt-autotime[j])
    autotime = autotime/1000000


    #Removes the trailing zeros.
    idauto = np.where(autotime != 0)[0]
    autotime = autotime[idauto]
    auto = auto[idauto,:,:]
    
    return auto, autotime


def delayTime2bin(dTimeArr, chanArr, chanNum, winInt):
    
    decayTime = np.array(dTimeArr)
    #This is the point and which each channel is identified.
    decayTimeCh =decayTime[chanArr == chanNum] 
    

    
    
    #Find the first and last entry
    firstDecayTime = 0;#np.min(decayTimeCh).astype(np.int32)
    tempLastDecayTime = np.max(decayTimeCh).astype(np.int32)
    
    #We floor this as the last bin is always incomplete and so we discard photons.
    numBins = np.floor((tempLastDecayTime-firstDecayTime)/winInt)
    lastDecayTime = numBins*winInt
    

    bins = np.linspace(firstDecayTime,lastDecayTime, int(numBins)+1)
    
    
    photonsInBin, jnk = np.histogram(decayTimeCh, bins)

    #bins are valued as half their span.
    decayScale = bins[:-1]+(winInt/2)

    #decayScale =  np.arange(0,decayTimeCh.shape[0])
   
    
    

    return list(photonsInBin), list(decayScale)
