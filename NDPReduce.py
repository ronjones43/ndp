# -*- coding: utf-8 -*-
"""
Neutron Depth Profiling Data Reduction
"""

import numpy as np
import math
import re
import os
import csv
from datetime import datetime


class ndp():
    """
    Class to process neutron depth profiling (NCNR) data related to a single sample
    Data is collected into a python dictionary (ndp.data) as ndp object is created
    Methods transform data and record new data in ndp.data
    ndp.data is intended to provide enough information to recreate the entire data reduction
    """
    
    def __init__(self):
        
        
        self.instrument = {
            "Configuration" : "Hello"
            }
        
        self.detector = {
            "Name" : "Lynx",
            "Channels" : np.arange(0,4096),
            "Energy" : np.zeros(4096),
            "Depth" : np.zeros(4096),
            "Corr Depth" : np.zeros(4096),
            "dDepth" : np.zeros(4096),
            "dDepth Uncert" : np.zeros(4096)
        }
        

        self.data = {
            "Sam Dat" : {
                "Files" : [],
                "Labels" : [],
                "Detector" : [],
                "Live Time" : 0.0,
                "Real Time" : 0.0,
                "Operations" : []
            },
            "Sam Mon" : {
                "Files" : [],
                "Labels" : [],
                "Detector" : [],
                "Live Time" : 0.0,
                "Real Time" : 0.0,
                "Operations" : []
            },
            "Bgd Dat" : {
                "Files" : [],
                "Labels" : [],
                "Detector" : [],
                "Live Time" : 0.0,
                "Real Time" : 0.0,
                "Operations" : []
            },
            "Bgd Mon" : {
                "Files" : [],
                "Labels" : [],
                "Detector" : [],
                "Live Time" : 0.0,
                "Real Time" : 0.0,
                "Operations" : []
            },
            "Ref Dat" : {
                "Files" : [],
                "Labels" : [],
                "Detector" : [],
                "Live Time" : 0.0,
                "Real Time" : 0.0,
                "Operations" : []
            },
            "Ref Mon" : {
                "Files" : [],
                "Labels" : [],
                "Detector" : [],
                "Live Time" : 0.0,
                "Real Time" : 0.0,
                "Operations" : []
            },
            "TRIM" : {
                "Files" : []
            },
        }
        
        self.atom = {
            "He" : {
                "Cross Section" : 5322.73,
                "Abundance" : 0.00000134
                },
            "Li" : {
                "Cross Section" : 939.09,
                "Abundance" : 0.0759
                },
            "B" : {
                "Cross Section" : 3600.48,
                "Abundance" : 0.196
                },
            "N" : {
                "Cross Section" : 1.86,
                "Abundance" : 0.99636
                },
            }

    
    def readconfig(self, path, configfilename = "NDPInstrumParms.dat"):
        """
        Read NDPReduce configuration file
        """
        
        filename = path + configfilename
        with open(filename) as f:
            lines = f.readlines()
            self.instrument["Configuration"] = lines[4][21:]
            self.instrument["Beam Energy"] = float(lines[5][18:])
            self.instrument["Num Channels"] = int(lines[6][19:])
            self.instrument["Zero Channel"] = int(lines[7][13:])
            self.instrument["Alpha Channels"] = [int(lines[9]), int(lines[10])]
            self.instrument["Calib Coeffs"] = np.array([float(lines[12]), float(lines[13])])
        
        return

    def runschema(self, path, schemafilename = "NDPDataSchema.dat"):
        

        datatypes=["TRIM", "Bgd Dat", "Bgd Mon", "Ref Dat", "Ref Mon", "Sam Dat", "Sam Mon"]
        pathline = [3, 7, 9, 13, 15, 19, 21] 
        fileline = [4, 8, 10, 14, 16, 20, 22]

        self.readschema(path, schemafilename, datatypes, pathline, fileline)
        
        self.evalTRIM(self.data['TRIM']['Path'])
        self.chan2depth()
        
        # Remove TRIM from datatypes
        datatypes=["Bgd Dat", "Bgd Mon", "Ref Dat", "Ref Mon", "Sam Dat", "Sam Mon"]
        for dt in datatypes:
             self.loadNDP(dt, self.data[dt]['Path'])
        
        self.deadtime()
        self.normalize()
        self.correct()
        self.ref_integrate()
        self.scale2ref()
        self.bin_channels()
        
        return
        
    def readschema(self, path, filename, datatypes, pathline, fileline):
        """
        Read NDPReduce Data Schema file, if full schema not already developed then build and save.
        """
                   
        with open((path+filename)) as f:
            lines = f.readlines()
        
        i=0
        for dt in datatypes:
            line = lines[int(pathline[i])].split(": ", 1)
            self.data[dt]["Path"] = line[1][:-1]
            filelist = os.listdir(self.data[dt]["Path"])
            line = lines[fileline[i]].split(": ", 1)
            self.data[dt]["Files"] = [x for x in filelist if line[1][:-1] in x] 
            i += 1
        
        return
    

    def evalTRIM(self, path):

        numfiles = len(self.data["TRIM"]["Files"])
        self.data["TRIM"]["Median KeV"] = np.zeros(numfiles+1)
        self.data["TRIM"]["Thick"] = np.zeros(numfiles+1)
        self.data["TRIM"]["Median KeV"][0] = self.instrument["Beam Energy"]
        self.data["TRIM"]["Thick"][0] = 0.0
        self.data["TRIM"]["Coeffs"] = np.zeros(3)
        
        # Regex to extract layer thickness in Angstroms from TRIM header (line 10)
        # p = re.compile(r'\(\s*[0-9]+\s*A\)')
    
        
        # Regex to extract energy from the third or fourth column of the TRIM file
        p = re.compile(r'\.[0-9]*E\+[0-9]*')
        
        # Regex to extract depth from the fourth or fifth column of the TRIM file
        q = re.compile(r'[0-9]*E-[0-9]*')
        
        
        for filenum in range(numfiles):
            trim_file = path + self.data["TRIM"]["Files"][filenum]
    
            with open(trim_file) as f:
                lines = f.readlines()
                num_lines = len(lines)-12
                ev = np.zeros(num_lines)
                depth = np.zeros(num_lines)
    
                i=0
                for line in lines[12:]:        
                    m = p.search(line)
                    ev[i] = float(m.group())
                    m = q.search(line)
                    depth[i] = float(m.group())
                    i += 1
                    
            self.data["TRIM"]["Median KeV"][filenum+1] = np.median(ev)/1000
            self.data["TRIM"]["Thick"][filenum+1] = np.average(depth)/10
            self.data["TRIM"]["Coeffs"] = np.polyfit(\
                self.data["TRIM"]["Median KeV"], self.data["TRIM"]["Thick"], 2)
        
        return
    
    
    def loadNDP(self, dt, path):
        """
        Function to load a list of NDP data files of a given datatype (Sam Dat, Sam Mon, etc),
        load header info and sum of counts/channel into ndp.data
        
        """

        filelist = self.data[dt]["Files"]
        numfiles = len(filelist)
        numchannels = self.instrument["Num Channels"]
        

        if("Channel Sum" not in self.data[dt]["Operations"]):
                self.data[dt]["Operations"].append("Channel Sum")
        
        for filenum in range(numfiles):
            ndp_file = path + filelist[filenum]
            with open(ndp_file) as f:
                lines = f.readlines() #reads all of the file into a numbered list of strings
                self.data[dt]["Detector"].append(lines[0][12:-1])
                self.data[dt]["Labels"].append(lines[1][8:-1])
                self.data[dt]["Live Time"] += float(lines[3][12:-1])
                self.data[dt]["Real Time"] += float(lines[4][12:-1])
            
                if(filenum<1): 
                    self.data[dt]["Datetime"] = \
                        datetime.strptime(lines[2][12:-10],'%a %b %y %H:%M:%S')
                    self.data[dt]["Counts"] = np.zeros(numchannels)
                
                for channel in range(numchannels):
                    counts = lines[channel+8].split()
                    self.data[dt]["Counts"][channel] += float(counts[1])
        
        return

    
    def deadtime(self, datatypes=["Sam Dat", "Sam Mon", "Bgd Dat", "Bgd Mon", "Ref Dat", "Ref Mon"]):
        """
        Returns a copy of ndp.data with deadtime corrected counts for each of the
        sample types. Optional argument to specify the datatypes.
        
        """

        old_settings = np.seterr(all='ignore')  #seterr to known value
        np.seterr(all='ignore')
    
        for datatype in datatypes:
            if("Deadtime Scaled" not in self.data[datatype]["Operations"]):
                self.data[datatype]["Operations"].append("Deadtime Scaled")
            livetime = self.data[datatype]["Live Time"]
            realtime = self.data[datatype]["Real Time"]
            self.data[datatype]["Dt ratio"] = livetime/realtime
            self.data[datatype]["Counts/Dt"] = self.data[datatype]["Counts"]*realtime/livetime
            self.data[datatype]["Counts/Dt Uncert"] = np.nan_to_num(np.divide(
                self.data[datatype]["Counts/Dt"],np.sqrt(self.data[datatype]["Counts"])))
    
        np.seterr(**old_settings)
    
        return

    def normalize(self, datatypes=["Sam Dat", "Bgd Dat", "Ref Dat"]):
        """
        Calculate (data file counts)/(monitor file counts)
    
        returns ndp_norm
        """

        old_settings = np.seterr(all='ignore')  #seterr to known value
        np.seterr(all='ignore')

        for dt in datatypes:
            if("Normalized" not in self.data[dt]["Operations"]):
                self.data[dt]["Operations"].append("Normalized")

            mon_type = dt[0:4]+"Mon"
            #Sum over range set to capture 10B alpha peaks (channels 1900-2900)
            lowchan, hichan = self.instrument["Alpha Channels"]
            mon_sum = np.sum(self.data[mon_type]["Counts/Dt"][lowchan:hichan])        
            self.data[dt]["Monitor"] = mon_sum
            self.data[dt]["Monitor Uncert"] = math.sqrt(mon_sum)    

            self.data[dt]["Norm Cts"] = self.data[dt]["Counts/Dt"]/self.data[dt]["Monitor"]
            x2 = np.nan_to_num(np.power(self.data[dt]["Counts/Dt Uncert"]/self.data[dt]["Counts/Dt"],2))
            y2 = math.pow(self.data[dt]["Monitor Uncert"]/self.data[dt]["Monitor"],2)
            self.data[dt]["Norm Cts Uncert"] = self.data[dt]["Norm Cts"]*np.sqrt(x2+y2)

        np.seterr(**old_settings)

        return
    

    def correct(self, datatypes=["Sam Dat", "Ref Dat"]):
        """
        Subtract background and return a corrected data file
        
        data_norm, bkgd_norm are normalized data objects from ndp_norm()
        """
    
        for dt in datatypes:
            if("Corrected" not in self.data[dt]["Operations"]):
                self.data[dt]["Operations"].append("Corrected")

            self.data[dt]["Corr Cts"] = self.data[dt]["Norm Cts"]-self.data["Bgd Dat"]["Norm Cts"]
            x2 = np.power(self.data[dt]["Norm Cts Uncert"],2)
            y2 = np.power(self.data["Bgd Dat"]["Norm Cts Uncert"],2)
            self.data[dt]["Corr Cts Uncert"] = np.sqrt(x2+y2)
    
        return

    def cross_sec(self, atom, datatype = ["Sam Dat"]):
        """
        Define the cross section of the sample
        """
        
        self.data[datatype]["Atom"] = "B"
        self.data[datatype]["Atom Cross Sec"] = 3600.48
        self.data[datatype]["Atom Conc"] = 5.22e15
        self.data[datatype]["Atom Conc Uncert"] = 3e13
        self.data[datatype]["Atom Branch Frac"] = 0.94
        self.data[datatype]["Atom Abundance"] = 0.196

            
    def ref_integrate(self, datatypes=["Ref Dat"]):
        """
        Integrate the alpha peaks of the reference data set
        Also, set atomic concentration field here for now
        """

        for dt in datatypes:
            if("Integrated Peaks" not in self.data[dt]["Operations"]):
                self.data[dt]["Operations"].append("Integrated Peaks")

            self.data[dt]["alpha*"] = np.sum(self.data[dt]["Corr Cts"][1791:2142])        
            self.data[dt]["alpha"] = np.sum(self.data[dt]["Corr Cts"][2291:2592])        
            cts_uncert2 = np.power(self.data[dt]["Corr Cts Uncert"], 2)
            self.data[dt]["alpha* Uncert"] = math.sqrt(np.sum(cts_uncert2[1791:2142]))
            self.data[dt]["alpha Uncert"] = math.sqrt(np.sum(cts_uncert2[2291:2592]))
            
        return
    
    
    def scale2ref(self, datatypes=["Sam Dat"]):
        """
        Use reference sample data to convert counts to number of atoms
        """

        old_settings = np.seterr(all='ignore')  #seterr to known value
        np.seterr(all='ignore')

        for dt in datatypes:
            if("Scaled to Reference" not in self.data[dt]["Operations"]):
                self.data[dt]["Operations"].append("Scaled to Reference")
                
            alpha_cts = self.data["Ref Dat"]["alpha*"]
            sample_cross = self.data[dt]["Atom Cross Sec"]
            ref_cross = self.data["Ref Dat"]["Atom Cross Sec"]
            ref_conc = self.data[dt]["Atom Conc"]
            branch_frac = self.data[dt]["Atom Branch Frac"]
            abundance = self.data[dt]["Atom Abundance"]
        
            scale_coeff = (ref_conc * ref_cross) / (alpha_cts * sample_cross)
            self.data[dt]["Atoms/cm2"] = scale_coeff * self.data[dt]["Corr Cts"]
            self.data[dt]["Atoms/cm2"] /= (branch_frac*abundance)
            
            ratio1 = math.pow(self.data["Ref Dat"]["alpha* Uncert"]/alpha_cts,2)
            ratio2 = math.pow(self.data["Ref Dat"]["Atom Conc Uncert"]/ref_conc,2)
            ratio3 = np.nan_to_num(np.power(self.data[dt]["Corr Cts Uncert"]/self.data[dt]["Corr Cts"], 2))
            self.data[dt]["Atoms/cm2 Uncert"] = self.data[dt]["Atoms/cm2"]*np.sqrt(ratio1 + ratio2 + ratio3)
            
            self.data[dt]["Atoms/cm3"] = np.nan_to_num(self.data[dt]["Atoms/cm2"]/self.detector["Del Depth"])

            ratio1 = np.nan_to_num(np.power(self.data[dt]["Atoms/cm2 Uncert"]/self.data[dt]["Atoms/cm2"],2))
            ratio2 = np.nan_to_num(np.power(self.detector["Del Depth Uncert"]/self.detector["Del Depth"],2))
            self.data[dt]["Atoms/cm3 Uncert"] = self.data[dt]["Atoms/cm3"]*np.sqrt(ratio1 + ratio2)

        np.seterr(**old_settings)

        return
    
    def bin_channels(self, bin_size=21):
        """
        Bin channels from ndp.detector
        """
    
        # Note that the last bin is not handled correctly as it will not necessarily have
        # the same number of channels as the other bins. To fix this would involve
        # some time and code testing. Assuming that the last bin is never interesting, but
        # perhaps we should eventually fix this just in case.
        #
        # Fix is in recalculating bin_size each time, or at least in the final bin.
        num_channels = self.instrument["Num Channels"]
        num_bins = int(num_channels/bin_size)+1
                
        self.detector["Energy Binned"] = np.zeros(num_bins)
        self.detector["Depth Binned"] = np.zeros(num_bins)
        self.data["Sam Dat"]["Atoms/cm2 Binned"] = np.zeros(num_bins)
        self.data["Sam Dat"]["Atoms/cm2 Binned Uncert"] = np.zeros(num_bins)
        self.data["Sam Dat"]["Atoms/cm3 Binned"] = np.zeros(num_bins)
        self.data["Sam Dat"]["Atoms/cm3 Binned Uncert"] = np.zeros(num_bins)

        uncert2_1 = np.power(self.data["Sam Dat"]["Atoms/cm2 Uncert"],2)
        uncert2_2 = np.power(self.data["Sam Dat"]["Atoms/cm3 Uncert"],2)

        for bin in range(num_bins-1):
            self.detector["Energy Binned"][bin] = np.median(self.detector["Energy"][bin*bin_size:(bin+1)*bin_size])
            self.detector["Depth Binned"][bin] = np.median(self.detector["Corr Depth"][bin*bin_size:(bin+1)*bin_size])
            self.data["Sam Dat"]["Atoms/cm2 Binned"][bin] = \
                np.average(self.data["Sam Dat"]["Atoms/cm2"][bin*bin_size:(bin+1)*bin_size])
            self.data["Sam Dat"]["Atoms/cm2 Binned Uncert"][bin] = \
                math.sqrt(np.sum(uncert2_1[bin*bin_size:(bin+1)*bin_size]))/bin_size
            self.data["Sam Dat"]["Atoms/cm3 Binned"][bin] = \
                np.average(self.data["Sam Dat"]["Atoms/cm3"][bin*bin_size:(bin+1)*bin_size])
            self.data["Sam Dat"]["Atoms/cm3 Binned Uncert"][bin] = \
                math.sqrt(np.sum(uncert2_2[bin*bin_size:(bin+1)*bin_size]))/bin_size
            
            
        # The last bin may have a different size, so need a separate calculation.
        # Note that this is untested code, but the last bin is rarely used
        self.detector["Energy Binned"][num_bins-1] = np.median(self.detector["Energy"][bin*bin_size:-1])
        self.detector["Depth Binned"][num_bins-1] = np.median(self.detector["Corr Depth"][bin*bin_size:-1])
        self.data["Sam Dat"]["Atoms/cm2 Binned"][num_bins-1] = \
                np.average(self.data["Sam Dat"]["Atoms/cm2"][bin*bin_size:-1])
        self.data["Sam Dat"]["Atoms/cm2 Binned Uncert"][num_bins-1] = \
                math.sqrt(np.sum(uncert2_1[bin*bin_size:-1]))/(num_channels%bin_size)
        self.data["Sam Dat"]["Atoms/cm3 Binned"][num_bins-1] = \
                np.average(self.data["Sam Dat"]["Atoms/cm3"][bin*bin_size:-1])
        self.data["Sam Dat"]["Atoms/cm3 Binned Uncert"][num_bins-1] = \
                math.sqrt(np.sum(uncert2_2[bin*bin_size:-1]))/(num_channels%bin_size)

        return

    
    
    def chan2depth(self):
        """
        Convert channels to energy and then to a relative depth with uncertainties
        Depth is based on the TRIM simulation but will have the incorrect origin
        """

        # These values change infrequently and are provided by the instrument scientist
        m, b = self.instrument["Calib Coeffs"]
        self.detector["Energy"] = (m*self.detector["Channels"]) + b

        # These values are derived from SRIM/TRIM, freeware used to calculate energy of generated ions in matter
        # Depth is in nanometers
        a, b, c = self.data["TRIM"]["Coeffs"]
        self.detector["Depth"] = a*np.power(self.detector["Energy"],2) \
            + b*self.detector["Energy"] + c
        
        # Zero channel is defined through the experimental setup
        zerochan = self.instrument["Zero Channel"]
        self.detector["Corr Depth"] = self.detector["Depth"] \
            - self.detector["Depth"][zerochan]
        
        # Del Depth in centimeters
        self.detector["Del Depth"] = np.zeros(len(self.detector["Corr Depth"]))
        for x in range(len(self.detector["Corr Depth"])-1):
            self.detector["Del Depth"][x] = 1e-7*(self.detector["Corr Depth"][x-1] - self.detector["Corr Depth"][x])

        self.detector["Del Depth Uncert"] = 0.05 * self.detector["Del Depth"]
        
        return

    def saveAtoms(self, path, filename):
        """
        Write six column CSV for atoms/cm2 and atoms/cm3
        """
        
        header = [['NIST Neutron Depth Profiling Data File'],
                  ['Sample Data Files'],
                  [self.data['Sam Dat']["Files"]],
                  ['Sample Monitor Files'],
                  [self.data['Sam Mon']["Files"]],
                  ['Background Data Files'],
                  [self.data['Bgd Dat']["Files"]],
                  ['Background Monitor Files'],
                  [self.data['Bgd Mon']["Files"]],
                  ['Reference Data Files'],
                  [self.data['Ref Dat']["Files"]],
                  ['Reference Monitor Files'],
                  [self.data['Ref Mon']["Files"]],
                  ['Sample Data Operations'],
                  [self.data['Sam Dat']['Operations']],
                  [self.data['Sam Dat']["Datetime"]],
                  [' '],
                  ['Energy (keV)', 'Depth (nm)', 'Atoms/cm2', 'Uncertainty', 'Atoms/cm3', 'Uncertainty']
                  ]
        
        numlines = len(self.detector['Energy Binned'])
    
        with open((path+filename), 'w', newline='') as csvfile:
            #using excel comma separated value format, can just click to open in excel
            #another option for dialect is excel-tab
            #custom dialects are possible in the csv class
            writer = csv.writer(csvfile, dialect = 'excel')
            for x in range(len(header)):
                writer.writerow(header[x]) 
            for x in range(numlines):
                data = [self.detector['Energy Binned'][x],
                        self.detector['Depth Binned'][x],
                        self.data['Sam Dat']['Atoms/cm2 Binned'][x],
                        self.data['Sam Dat']['Atoms/cm2 Binned Uncert'][x],
                        self.data['Sam Dat']['Atoms/cm3 Binned'][x],
                        self.data['Sam Dat']['Atoms/cm3 Binned Uncert'][x]
                ]                
                writer.writerow(data) 
            
        return