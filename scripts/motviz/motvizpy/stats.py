#!/usr/bin/env python3.7

import numpy as np
import pandas as pd
from Bio import SeqIO
import math
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.signal import argrelextrema
from pathlib import Path
from collections import Counter
from Bio import AlignIO
import re

def seq_extract(in_file, file_ext): 
    """Extrct the sequence from the fasta file
    
    Args: 
        in_file [str]: Input file address
        
    Returns: 
        seqs [1d list]: Protein sequences lisst
        
    """
    if file_ext == "sth": 
        file_ext = "stockholm"
        
    elif file_ext == "aln" or file_ext == "clustal": 
        file_ext = "clustal"  
         
    alignment = AlignIO.read(in_file, file_ext)    
    seqs = {i.id : str(i.seq) for i in alignment}

    return seqs

class Analysis: 
    """Class will calculate conservation, visualize, and write PyMol script.
    
    Args: 
        seq [1d list]: Sequences of amino acids from fasta file 
    
    """  
    def seq2np(self): 
        """"Turn the sequence into numpy S1 array for calculations later. 
        
        Args: 
            seq [2d list]: List of lists that contain sequences 
        
        Returns: 
            np array [2d np array]: Np array that turns the chars into bytes
            
        """
        
        return np.asarray(self.seq, dtype='S1')
              
    def __init__(self, seq, pdb_id): 
        """Initialize class Analysis. 
        
        Convert the 2d list to np array and make accessible
        globally for other other functions. 
        
        Args: 
            seq [list of lists]: 2d list of sequences
            pdb_id [str]: PDB ID that will be written in the 
                    final PyMol script file.  
            
        """   
        self.seq = seq
        self.pdb_id = pdb_id
        
    def _shannon(self, array): 
        """Calculate Shannon Entropy vertically via loop. 
        
        Args: 
            array [nd array]: 1d array of sequences from all the species
        
        Returns: 
            entropy [nd float array]: Per column value for each position vertically
        
        """
        
        aa_count = Counter(array)
        max_value = max(aa_count.values())
        
        pA = 1
        for k, v in aa_count.items(): 
            pA *= (v / 5)
        
        return -np.sum(pA*np.log2(pA))
        
        
        
    def conservation_score(self, np_seq): 
        """Calculate the Shannon Entropy vertically
        for each position in the amino acid msa sequence.
        
        Args: 
            np_seq [Numpy nd array]: Np array of sequences
            
        Returns: 
            np apply array [nd float array]: Calculate conservation 
            scores vertically into a float nd array   
        """
        
        return np.apply_along_axis(self._shannon, 0, np_seq)      

    def normalize_data(self, ent_list): 
        """Takes the entropy array and normalizes the data. 
        
        Args: 
            ent_list [Nd array]: Entropy float array
            
        Returns: 
            Normalized list [nd array]: Values between -1 and 1
            
        """
        
        return (2.*(ent_list - \
            np.min(ent_list))/np.ptp(ent_list)-1)       
        
    
    def find_local_minima(self, data): 
        """Find local minima that are lower than mean of data
        
        Args: 
            data [nd float array]: Normalized conservation data
            
        Returns: 
            polished_minima [list]: List that contains minima 
            lower than the mean.
            
        """
        
        local_minima = argrelextrema(data, np.less)
        data_mean = np.mean(data)
        polished_minima = []
        for i in local_minima: 
            for j in i: 
                if data[j] < data_mean: 
                    polished_minima.append(j)
        
        return polished_minima

    def moving_average(self, data, n=3) :
        """Calculated the rolling average of teh data

        Args: 
            data [numpy nd array]: Float array of the conservation score calculated
            n [int]: Rolling average wegith

        Returns: 
            avg_data [numpy nd array]: Float array of rolling average
    
        """
        avg_data = np.cumsum(data, dtype=float)
        avg_data[n:] = avg_data[n:] - avg_data[:-n]

        return avg_data[n - 1:] / n

    def find_motif(self, data, minima, threshold): 
        """Given the minima and data, look for consecutive
        set (word size of 4) of values that are 1/4th of the mean. 
        
        Args; 
            data [nd float array]: Normalized conservation daa
            minima [1d list]: List of minima lower than the mean 
            threshold [float]: Threshold value below which all 
                consecutive values whill be taken up as motifs 
                        
        Returns: 
            pos_motif [1d list]: Possible motifs that have 4 consecutive 
                lower scores than 1/4th of the mean, only the 1st index. 
                
            pos [1d list]: Positions of these motifs.        
             
        """
        
        pos_motif = []
        pos = []

        for i in minima: 
            if i - 4 > 0: 
                motif_stretch = data[i - 1 : i + 1]
                if np.all(motif_stretch < threshold): 
                    # Take the first value. 
                    pos_motif.append(motif_stretch[0])
                    pos.append(i)
                       
        return (pos_motif, pos)
    
    def csv_writer(self, file, cons_data): 
        """Write the conservation data on a a CSV file
        
        Args: 
            file [str]: File path to where the data should be written
            cons_data [dict]: Amino acid position as key and conservation value as value
            
        """
        cons_data = {k:v for k, v in cons_data.items() if v > 0.50}        
        df = pd.DataFrame.from_dict(cons_data, orient="index")
        df.index.name = "Nucleotide position"
        df.columns = ["Variation score"]
        df.to_csv(file)
    
    def pymol_script_writer(self, out_file, pos): 
        """Motifs that are found are then written a txt file.
        Thhis is then run on PyMol by typing the following on terminal: 
            @pymol_script.txt 
        
        Args: 
            out_file [str]: Address for where the file should be written
            pos [1d list]: Posiitons of the motifs as list
            
        """
        
        path = Path(out_file)
        with open(path, "w") as file: 
            file.write(f"fetch {self.pdb_id}\n\n")
            for i,_ in enumerate(pos): 
                file.write(f"create mot{pos[i]}, resi {pos[i]}-{pos[i]+4} \n")
                
            file.write("\nhide_all\n")
            file.write("\n")
            for i,_ in enumerate(pos): 
                file.write(f"show cartoon, resi{pos[i]}\n")
            file.write("\n")
            for i,_ in enumerate(pos): 
                file.write(f"color red, mot{pos[i]}\n")
        


def main(): 
    orig_file = Path("/home/nadzhou/Desktop/1yu5.fasta")
    seq_dict = seq_extract("/home/nadzhou/Desktop/omega.aln", "clustal")
    seq = [[x for x in y] for y in seq_dict.values()]
    c = Analysis(seq, "1xef")

    c_ent = c.conservation_score(c.seq2np())


    norm_data = c.normalize_data(c_ent)


    norm_data = c.moving_average(norm_data)

    norm_data_len = [i for i,_ in enumerate(norm_data)]
    minima = c.find_local_minima(norm_data)
    
    pos_motif, pos = c.find_motif(norm_data, minima, 4)
    
    seq2 = c.original_file_seq_extract(orig_file)

    seq_residues = c.find_motif_pos(pos,  seq2)    

    plotter = {}

    for i in seq_residues: 
        for k, v in seq_dict.items(): 
            if i in v: 
                plotter[k] = i




if __name__ == "__main__": 
    main()

