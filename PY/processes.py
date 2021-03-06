################################################################################
'''Module "processes", July 2010, is part of
BETR-Research by Harald von Waldow <hvwaldow@chem.ethz.ch>.

This module contains the process definitions and calculates D-values for
intra-region processes of a particular model parametrization'''
################################################################################

from numpy import *
import inspect
import copy
from globalz import *
import sys

class process():
    ''' The class contains the intra-region process descriptions of
    BETR-Global as methods. Each method returns a dictionary
    containing D-values associated with the process identified by the
    dictionary keys:
    
      {(*from_compartmentID*, *to_compartmentID*, *processname*) : *D*},
    
    where *processname* is identical to the name of the method and *D*
    is the associated D-value [Pa/m^3/h]. Upon initialization, the
    class checks whether all processes in *model.proclist* are
    implemented. The class provides the method
    :py:meth:`~processes.process.getD` that calls all process
    description methods and returns a dictionary containing *all*
    process D-values'''
    
    def __init__(self, model):
        self.m=model
        self.D={}
        ## calculation of D-values##
        ## check whether all processes are implemented
        self.plist=[x[0] for x in self.m.proclist]
        for p in self.plist:
            try:
                getattr(self,p)
            except AttributeError:
                print("processes.py: "
                      +"Method %s not implemented !\n Aborting!") % (p)
                sys.exit(1)

    def getD(self):
        ''' construct dictionary with D-values for all intra-cell processes '''
        
        for p in self.plist:
            self.D.update(getattr(self,p)())
        return(self.D)
 
    def betr_degradation(self):
        ''' degradation '''
        # don't change this
        D={}
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        for c in self.m.compdict.keys():
            D[(c,c,procname)]=self.m.chempardict[c]['k_reac']\
                                 *self.m.vdict[c]['bulk']\
                                 *self.m.zdict[c]['bulk']
        # degradation in air only in gas phase ?
        if self.m.controldict['aerosoldeg'] in ['0','False','false','f','FALSE'
                                                'F','No','no','n','NO']:
            D[(1,1,procname)]=self.m.chempardict[1]['k_reac']\
                                   *self.m.vdict[1]['bulk']\
                                   *self.m.zdict[1]['air']
            D[(2,2,procname)]=self.m.chempardict[2]['k_reac']\
                                   *self.m.vdict[2]['bulk']\
                                   *self.m.zdict[2]['air']
        return(D)
     
    def betr_advectiveloss(self):
        ''' advective loss from the system '''
        # don't change this
        D={}
        ## soil convection
        ## ATT: what is factor 0.05 ? Correction for vert. conc. profile ?
        D[(6,6,'burial')]=0.05*self.m.par['convec6solids']\
                               *self.m.par['A']*self.m.par['perc6']\
                               *self.m.zdict[6]['solids']
        ### leaching from soil (loss from system)
        #D[(6,6,'leach')]=self.m.par['leach6']\
                              #*self.m.par['A']*self.m.par['perc6']\
                              #*self.m.zdict[6]['water']      
        ## leaching from soil (loss from system)
        # Modified by HW: leach6 = prec - runoff
        # To be improved: leach6 = prec - runoff - evaporation - dsnow
        D[(6,6,'leach')]=(self.m.par['precip']-self.m.par['runoff6water'])\
                              *self.m.par['A']*self.m.par['perc6']\
                              *self.m.zdict[6]['water']
        ## sediment burial
        #SSchenker This should be equal to the sedimentation - resusp rate
#        D[(7,7,'burial')]=self.m.par['A']*self.m.par['perc4']\
#                               *self.m.par['seddep']*self.m.zdict[4]['sussed']
#       Change not accepted
#       
        D[(7,7,'burial')]=self.m.par['sedburial']\
                               *self.m.par['A']*self.m.par['perc4']\
                               *self.m.zdict[7]['solids']
        ## diffusion to stratosphere
        D[(1,1,'stratosphere')]=self.m.par['diffstrato']*self.m.par['A']\
                                     *self.m.zdict[1]['air']
        ## sedimentation in ocean
        D[(5,5,'sedimentation')]=self.m.par['partsink5']\
                                      *self.m.par['A']*self.m.par['perc5']\
                                      *self.m.zdict[5]['sussed']
        return(D)

    def betr_air1_air2_mix(self):
        ''' mixing between upper and lower atmosphere '''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        D[(1,2,procname)]=self.m.par['A']*self.m.par['mixing12']\
                           *self.m.zdict[1]['bulk']
        try: 
            D[(2,1,procname)]=self.m.par['A']*self.m.par['mixing21']\
                           *self.m.zdict[2]['bulk']
        except  ValueError: # SSchenker backward compatibility
            D[(2,1,procname)]=self.m.par['A']*self.m.par['mixing12']\
                           *self.m.zdict[2]['bulk'] 
        # 'mixing 21' added by HW in February 2013
        # by default the same as 'mixing12' and in const_parameters 
        # option to define in seasonal_parameters, using omega

        return(D)
      
    def betr_air2_veg_diff(self):
        ''' diffusive air-vegetation exchange according to
        Cousins and Mackay, 2001 [1]_.'''
        #don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        logpc=(-3.47-2.79*log10(self.m.chemdict['molmass'])\
                +0.97*log10(self.m.chempardict[2]['Kow'])\
                -11.2+0.704*log10(self.m.chempardict[2]['Kow'])
               ) / 2
        pc=10**logpc
        mtcavv=3600*pc/self.m.chempardict[2]['Kaw']
        A=self.m.par['A']*self.m.par['perc6']*self.m.par['perc3']\
           *self.m.par['LAI']
        Apos=where(A>0) # prevent division by zero errors
        d=zeros(A.shape)
        dc=A*mtcavv*self.m.zdict[3]['bulk']
        da=A*self.m.par['mtcairvegair']*self.m.zdict[2]['air']
        d[Apos]=(1/dc[Apos]+1/da[Apos])**-1
        # ATT : speed-limit to diffusion to a char. time > 8h
        # ATT : not clear to me, why veg->air, not air->veg
        # ATT : or both ?
        d=minimum(d,self.m.zdict[3]['bulk']*self.m.vdict[3]['bulk']/8.0)
        D[(2,3,procname)]=d
        # suppress secondary re-emission from surface compartments ? (non-default)
        if self.m.controldict['secondarySupr'] in ['1','True','true','t','TRUE'
                                                'T','Yes','yes','y','YES']:
            D[(3,2,procname)]=zeros(self.m.par['A'].shape)
        else:
            D[(3,2,procname)]=d     
        return(D)
    
    def betr_air2_veg_drydep(self):
        '''dry deposition to vegetation'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        A=self.m.par['A']*self.m.par['perc6']*self.m.par['perc3']
        D[(2,3,procname)]=A*self.m.par['fp2']*self.m.par['mtcaerosol']\
                         *self.m.zdict[2]['aerosol']
        return(D)

    def betr_air2_veg_dissolution(self):
        ''' air-vegetation rain dissolution (*the returned D-value
        refers to rain intensity during event (stwet)*)'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        A=self.m.par['A']*self.m.par['perc6']*self.m.par['perc3']
        # rain rate during precipitation events
        # deal here with stwet == 0, and inconsistencies in the
        # BETR Global paramterisation, where stwet=0 but precip > 0
        norainmask = self.m.par['stwet'] == 0
        stwet_tmp=copy.copy(self.m.par['stwet'])
        stwet_tmp[norainmask]=1
        mtc_event=self.m.par['precip']\
                   *(self.m.par['stdry']+self.m.par['stwet'])/stwet_tmp
        mtc_event[norainmask]=0
        D[(2,3,procname)]=A*mtc_event*self.m.zdict[2]['rain']\
                           *self.m.par['intercept']
        return(D)
    
    def betr_air2_veg_wetparticle(self):
        ''' wet particle deposition to vegetation
        (*the returned D-value refers to rain intensity during event (stwet)*)'''
         # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        A=self.m.par['A']*self.m.par['perc6']*self.m.par['perc3']
        # rain rate during precipitation events
        # deal here with stwet == 0, and inconsistencies in the
        # BETR Global paramterisation, where stwet=0 but precip > 0
        norainmask = self.m.par['stwet'] == 0
        stwet_tmp=copy.copy(self.m.par['stwet'])
        stwet_tmp[norainmask]=1
        mtc_event=self.m.par['precip']\
                   *(self.m.par['stdry']+self.m.par['stwet'])/stwet_tmp
        mtc_event[norainmask]=0
        D[(2,3,procname)]=A*mtc_event*self.m.zdict[2]['aerosol']\
                       *self.m.par['scavrat']*self.m.par['fp2']\
                       *self.m.par['intercept']
        return(D)

    def betr_air2_freshwater_diff(self):
        '''diffusive exchange air-freshwater'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        # HW changed self.m.zdict[2]['air'] to self.m.zdict[4]['air']
        D[(2,4,procname)]=self.m.par['A']*self.m.par['perc4']\
                        *((self.m.par['mtc4air']*self.m.zdict[4]['air'])**-1\
                          +(self.m.par['mtc4water']\
                            *self.m.zdict[4]['water'])**-1)**-1
        # suppress secondary re-emission from surface compartments ? (non-default)
        if self.m.controldict['secondarySupr'] in ['1','True','true','t','TRUE'
                                                'T','Yes','yes','y','YES']:
            D[(4,2,procname)]=zeros(self.m.par['A'].shape)
        else:
            D[(4,2,procname)]=D[(2,4,procname)]          
        return(D)

    def betr_air2_freshwater_drydep(self):
        ''' dry particle deposition to fresh water'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        D[(2,4,procname)]=self.m.par['A']*self.m.par['perc4']\
                        *self.m.par['fp2']*self.m.par['mtcaerosol']\
                        *self.m.zdict[2]['aerosol']
        return(D)

    def betr_air2_freshwater_dissolution(self):
        '''air-freshwater rain dissolution
         (*the returned D-value refers to rain intensity during event (stwet)*)'''
         # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        # rain rate during precipitation events
        # deal here with stwet == 0, and inconsistencies in the
        # BETR Global paramterisation, where stwet=0 but precip > 0
        norainmask = self.m.par['stwet'] == 0
        stwet_tmp=copy.copy(self.m.par['stwet'])
        stwet_tmp[norainmask]=1
        mtc_event=self.m.par['precip']\
                   *(self.m.par['stdry']+self.m.par['stwet'])/stwet_tmp
        mtc_event[norainmask]=0
        D[(2,4,procname)]=self.m.par['A']*self.m.par['perc4']\
                           *mtc_event*self.m.zdict[2]['rain']
        return(D)

    def betr_air2_freshwater_wetparticle(self):
        '''air-freshwater wet particle deposition
        (*the returned D-value refers to rain intensity during event (stwet)*)'''
         # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        # rain rate during precipitation events
        # deal here with stwet == 0, and inconsistencies in the
        # BETR Global paramterisation, where stwet=0 but precip > 0
        norainmask = self.m.par['stwet'] == 0
        stwet_tmp=copy.copy(self.m.par['stwet'])
        stwet_tmp[norainmask]=1
        mtc_event=self.m.par['precip']\
                   *(self.m.par['stdry']+self.m.par['stwet'])/stwet_tmp
        mtc_event[norainmask]=0
        D[(2,4,procname)]=self.m.par['A']*self.m.par['perc4']*mtc_event\
                        *self.m.zdict[2]['aerosol']*self.m.par['fp2']\
                        *self.m.par['scavrat']
        return(D)

    def betr_air2_ocean_diff(self):
        '''diffusive exchange air-ocean water'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here                                       
        # HW added 'perc8'. Simple pot-lid assumption.
        # HW changed self.m.zdict[2]['air'] to self.m.zdict[5]['air']
        try: #Backward compatibility
            D[(2,5,procname)]=self.m.par['A']*self.m.par['perc5']*\
                        (1-self.m.par['perc8'])\
                        *((self.m.par['mtc25air']*self.m.zdict[5]['air'])**-1\
                        +(self.m.par['mtc25water']\
                        *self.m.zdict[5]['water'])**-1)**-1
        
        except     ValueError:
             D[(2,5,procname)]=self.m.par['A']*self.m.par['perc5']\
                        *((self.m.par['mtc25air']*self.m.zdict[2]['air'])**-1\
                          +(self.m.par['mtc25water']\
                            *self.m.zdict[5]['water'])**-1)**-1
        
        # suppress secondary re-emission from surface compartments ? (non-default)
        if self.m.controldict['secondarySupr'] in ['1','True','true','t','TRUE'
                                                'T','Yes','yes','y','YES']:
            D[(5,2,procname)]=zeros(self.m.par['A'].shape)
        else:
            D[(5,2,procname)]=D[(2,5,procname)]
        return(D)


    def betr_air2_ocean_drydep(self):
        ''' dry particle deposition to ocean water'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here                                       
        # HW added 'perc8'. Simple pot-lid assumption.
        try: 
            D[(2,5,procname)]=self.m.par['A']*self.m.par['perc5']*\
                        (1-self.m.par['perc8'])\
                        *self.m.par['fp2']*self.m.par['mtcaerosol']\
                        *self.m.zdict[2]['aerosol']
        except ValueError:
            D[(2,5,procname)]=self.m.par['A']*self.m.par['perc5']\
                        *self.m.par['fp2']*self.m.par['mtcaerosol']\
                        *self.m.zdict[2]['aerosol']
        return(D)

    def betr_air2_ocean_dissolution(self):
        '''air-ocean water rain dissolution
        (*the returned D-value refers to rain intensity during event (stwet)*)'''
         # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # rain rate during precipitation events
        # deal here with stwet == 0, and inconsistencies in the
        # BETR Global paramterisation, where stwet=0 but precip > 0
        # HW added 'perc8'. Simple pot-lid assumption.
        norainmask = self.m.par['stwet'] == 0
        stwet_tmp=copy.copy(self.m.par['stwet'])
        stwet_tmp[norainmask]=1
        mtc_event=self.m.par['precip']\
                   *(self.m.par['stdry']+self.m.par['stwet'])/stwet_tmp
        mtc_event[norainmask]=0                                                 
        try : #SSchenker backward compatibility
            D[(2,5,procname)]=self.m.par['A']*self.m.par['perc5']*\
                            (1-self.m.par['perc8'])\
                            *mtc_event*self.m.zdict[2]['rain']
        except ValueError:
            D[(2,5,procname)]=self.m.par['A']*self.m.par['perc5']\
                           *mtc_event*self.m.zdict[2]['rain']
        return(D)

    def betr_air2_ocean_wetparticle(self):
        '''air-ocean water wet particle deposition
        (*the returned D-value refers to rain intensity during event (stwet)*)'''
         # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        # rain rate during precipitation events
        # deal here with stwet == 0, and inconsistencies in the
        # BETR Global paramterisation, where stwet=0 but precip > 0
        # HW added 'perc8'. Simple pot-lid assumption.
        norainmask = self.m.par['stwet'] == 0
        stwet_tmp=copy.copy(self.m.par['stwet'])
        stwet_tmp[norainmask]=1
        mtc_event=self.m.par['precip']\
                   *(self.m.par['stdry']+self.m.par['stwet'])/stwet_tmp
        mtc_event[norainmask]=0                                                 
        try: 
            D[(2,5,procname)]=self.m.par['A']*self.m.par['perc5']*\
                        (1-self.m.par['perc8'])*mtc_event\
                        *self.m.zdict[2]['aerosol']*self.m.par['fp2']\
                        *self.m.par['scavrat']
        except ValueError:
                D[(2,5,procname)]=self.m.par['A']*self.m.par['perc5']*mtc_event\
                        *self.m.zdict[2]['aerosol']*self.m.par['fp2']\
                        *self.m.par['scavrat']                        
        return(D)
    
    def betr_air2_soil_diff(self):
        '''diffusive exchange air-soil'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here   
        A6pos=where(self.m.par['perc6']>0)  # HW: prevent division by zero errors
        d=zeros(self.m.par['A'].shape)
        if self.m.controldict['plowingEnhance'] in ['1', 'True', 'true', 't', 'TRUE'
                                                    'T', 'Yes', 'yes', 'y', 'YES']: 
            # HW: including plowing enhancement, according to 
            # self.m.zdict[2]['air'] changed to self.m.zdict[6]['air']
            # 'tspe' = time since last plowing event, see seasonal_parameters file
            dsa=self.m.par['A']*self.m.par['perc6']*sqrt(self.m.par['h6'])\
             *(sqrt(self.m.par['diff6air'])*self.m.zdict[6]['air']\
             +sqrt(self.m.par['diff6water'])*self.m.zdict[6]['water']\
             +sqrt(self.m.par['convec6solids'])*self.m.zdict[6]['solids'])\
             /sqrt(pi*self.m.par['tspe'])
        else: # Old version without plowing enhancement
            dsa=self.m.par['A']*self.m.par['perc6']\
             *(self.m.par['diff6air']*self.m.zdict[6]['air']\
             +self.m.par['diff6water']*self.m.zdict[6]['water']\
             +self.m.par['convec6solids']*self.m.zdict[6]['solids'])
             
        das=self.m.par['A']*self.m.par['perc6']\
             *self.m.par['mtc6air']*self.m.zdict[6]['air']
        d[A6pos]=(1/dsa[A6pos] + 1/das[A6pos])**-1
        D[(2,6,procname)]=d
        # D[(2,6,procname)]=(1/dsa + 1/das)**-1
        # suppress secondary re-emission from surface compartments ? (non-default)
        if self.m.controldict['secondarySupr'] in ['1','True','true','t','TRUE'
                                                'T','Yes','yes','y','YES']:
            D[(6,2,procname)]=zeros(self.m.par['A'].shape)
        else:
            D[(6,2,procname)]=D[(2,6,procname)]
        return(D)
    
    
    def betr_air2_soil_drydep(self):
        ''' dry particle deposition to soil'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        D[(2,6,procname)]=self.m.par['A']*self.m.par['perc6']\
                        *self.m.par['fp2']*self.m.par['mtcaerosol']\
                        *self.m.zdict[2]['aerosol']*(1-self.m.par['perc3'])
        return(D)

    def betr_air2_soil_dissolution(self):
        '''air-soil rain dissolution
        (*the returned D-value refers to rain intensity during event (stwet)*)'''
         # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        # rain rate during precipitation events
        # deal here with stwet == 0, and inconsistencies in the
        # BETR Global paramterisation, where stwet=0 but precip > 0
        norainmask = self.m.par['stwet'] == 0
        stwet_tmp=copy.copy(self.m.par['stwet'])
        stwet_tmp[norainmask]=1
        mtc_event=self.m.par['precip']\
                   *(self.m.par['stdry']+self.m.par['stwet'])/stwet_tmp
        mtc_event[norainmask]=0
        D[(2,6,procname)]=self.m.par['A']*self.m.par['perc6']\
                           *mtc_event*self.m.zdict[2]['rain']
        return(D)

    def betr_air2_soil_wetparticle(self):
        '''air-soil wet particle deposition
        (*the returned D-value refers to rain intensity during event (stwet)*)'''
         # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        # rain rate during precipitation events
        # deal here with stwet == 0, and inconsistencies in the
        # BETR Global paramterisation, where stwet=0 but precip > 0
        norainmask = self.m.par['stwet'] == 0
        stwet_tmp=copy.copy(self.m.par['stwet'])
        stwet_tmp[norainmask]=1
        mtc_event=self.m.par['precip']\
                   *(self.m.par['stdry']+self.m.par['stwet'])/stwet_tmp
        mtc_event[norainmask]=0
        D[(2,6,procname)]=self.m.par['A']*self.m.par['perc6']*mtc_event\
                        *self.m.zdict[2]['aerosol']*self.m.par['fp2']\
                        *self.m.par['scavrat']
        return(D)

    def betr_vegetation_soil_litter(self):
        '''vegetation-soil tranfer through litterfall'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        D[(3,6,procname)]=self.m.vdict[3]['bulk']*self.m.zdict[3]['bulk']\
                        /self.m.par['tauveg']
        return(D)

    def betr_freshwater_ocean_runoff(self):
        ''' fresh water to ocean runoff'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        # calculate river flow from freshwater to ocean in the same cell
        mflow=zeros(self.m.par.shape)
        sameregid=where(self.m.flowdict[(4,5)][:,0]
                        ==self.m.flowdict[(4,5)][:,1])[0]
        samereg=self.m.flowdict[(4,5)][sameregid,0].astype('int')
        mflow[samereg-1,:]=self.m.flowdict[(4,5)][sameregid,2:]
        ### ATT: BETR-Global:
        # calculate runoff from soil to ocean;
        # use max(soil_runoff, riverflow) for D-value
        soilrunoff=self.m.par['A']*self.m.par['perc6']\
                    *self.m.par['runoff6water']
        oceanmask=array(self.m.vdict[5]['bulk'] > 0).astype(int)
        freshwatermask=array(self.m.vdict[4]['bulk'] > 0).astype(int)
        soilrunoff=soilrunoff*oceanmask*freshwatermask
        flow=maximum(mflow, soilrunoff)
        D[(4,5,procname)]=self.m.zdict[4]['bulk']*flow
        return(D)
    
    def betr_ocean_sinkflux(self):
        ''' ocean water sinkflux (downwelling)'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        # calculate river flow from freshwater to ocean in the same cell
        mflow=zeros(self.m.par.shape)
        sameregid=where(self.m.flowdict[(5,5)][:,0]
                        ==self.m.flowdict[(5,5)][:,1])[0]
        samereg=self.m.flowdict[(5,5)][sameregid,0].astype('int')
        mflow[samereg-1,:]=self.m.flowdict[(5,5)][sameregid,2:]
        D[(5,5,procname)]=self.m.zdict[5]['bulk']*mflow
        return(D)   
    
    def betr_freshwater_sediment_diff(self):
        ''' freshwater-sediment diffusion '''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        D[(4,7,procname)]=self.m.par['A']*self.m.par['perc4']\
                           *self.m.par['diff7water']*self.m.zdict[4]['water']
        D[(7,4,procname)]=D[(4,7,procname)]
        return(D)

    def betr_freshwater_sediment_deposit(self):
        ''' freshwater-sediment particle sedimentation '''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here  
        # SSchenker Note pupms into sediment ... why?
        D[(4,7,procname)]=self.m.par['A']*self.m.par['perc4']\
                           *self.m.par['seddep']*self.m.zdict[4]['sussed']
        return(D)
        

    def betr_ocean_air_resusp(self):
        ''' marine aerosol production'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here              
        # HW added 'perc8'. Simple pot-lid assumption.
        # suppress secondary re-emission from surface compartments ? (non-default)
        if self.m.controldict['secondarySupr'] in ['1','True','true','t','TRUE'
                                                'T','Yes','yes','y','YES']:
            D[(5,2,procname)]=zeros(self.m.par['A'].shape)
        else:
            try:
                D[(5,2,procname)]=self.m.par['A']*self.m.par['perc5']\
                    *(1-self.m.par['perc8'])\
                    *self.m.par['prodaerosol5']*self.m.zdict[5]['water']
            except ValueError:
                D[(5,2,procname)]=self.m.par['A']*self.m.par['perc5']\
                    *self.m.par['prodaerosol5']*self.m.zdict[5]['water']
                            
        return(D)
    
    def betr_soil_air_resusp(self):
        ''' terrestrial aerosol production'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        # suppress secondary re-emission from surface compartments ? (non-default)
        if self.m.controldict['secondarySupr'] in ['1','True','true','t','TRUE'
                                                'T','Yes','yes','y','YES']:
            D[(6,2,procname)]=zeros(self.m.par['A'].shape)
        else:
            D[(6,2,procname)]=self.m.par['A']*self.m.par['perc6']\
                           *self.m.par['resusp6']*self.m.zdict[6]['solids']
        return(D)

    def betr_soil_veg_rootuptake(self):
        ''' soil-vegetation root uptake. The transpiration stream concentration
        factor (TSCF) is calculated according to Cousins and Mackay, 2001 [1]_.'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        TSCF = 0.784*exp(-((log10(self.m.chempardict[6]['Kow'])-1.78)**2)/2.44)
        D[(6,3,procname)]=self.m.par['A']*self.m.par['perc6']\
                           *self.m.par['perc3']*self.m.par['LAI']\
                           *TSCF*self.m.par['vegwateruptake']\
                           *self.m.zdict[6]['water']
        return(D)

    def betr_soil_freshwater_runoff(self):
        ''' water-runoff from soil to freshwater-bodies '''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        freshwatermask=array(self.m.vdict[4]['bulk'] > 0).astype(int)
        D[(6,4,procname)]=freshwatermask*self.m.par['A']*self.m.par['perc6']\
                           *self.m.par['runoff6water']*self.m.zdict[6]['water']
        return(D)

    def betr_soil_freshwater_erosion(self):          # HW: adapted to monthly runoff
        ''' solids-runoff from soil to freshwater-bodies'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        freshwatermask=array(self.m.vdict[4]['bulk'] > 0).astype(int)
        # process description starts here
        D[(6,4,procname)]=freshwatermask*self.m.par['A']*self.m.par['perc6']\
                           *self.m.par['runoff6solids']\
                           *self.m.zdict[6]['solids']
        return(D)

    def betr_sediment_freshwater_resusp(self):
        ''' sediment resuspension in freshwater bodies'''
        # don't change this
        procname=inspect.getframeinfo(inspect.currentframe())[2]
        D={}
        # process description starts here
        D[(7,4,procname)]=self.m.par['A']*self.m.par['perc4']\
                           *self.m.par['sedresup']*self.m.zdict[7]['solids']
        return(D)

    def betr_intermittent_rain(self):
        ''' Jolliet-Hauschild [2]_ calculation of intermittent rainfall.
        Uses the simplification implemented in BETR-Global.'''
        def _do_jolliet(wa,dwet,ddiss,twet,tdry,tsum):
            dj1=wa*tsum/tdry
            dj2=(dwet+ddiss)*twet/tsum
            dj1mask=(dj1 > dj2).astype(int)
            dj2mask=logical_not(dj1mask).astype(int)
            ddissnew=dj1mask*ddiss*twet/tsum\
                      +dj2mask*dj1*ddiss/dj2*twet/tsum
            dwetnew=dj1mask*dwet*twet/tsum\
                     +dj2mask*dj1*dwet/dj2*twet/tsum
            return([dwetnew,ddissnew])
            
        ## air-veg
        dwetairveg=copy.copy(self.D[(2,3,'betr_air2_veg_wetparticle')])
        ddissairveg=copy.copy(self.D[(2,3,'betr_air2_veg_dissolution')])
        mask=where((self.m.par['stdry'] != 0) & (self.m.par['stwet'] != 0)
                   & (dwetairveg != 0) & (ddissairveg != 0))
        tdry=self.m.par['stdry'][mask]
        twet=self.m.par['stwet'][mask]
        tsum=tdry+twet
        wa=self.m.vdict[2]['bulk'][mask]*self.m.zdict[2]['bulk'][mask]\
            *2/tdry*self.m.par['perc6'][mask]*self.m.par['perc3'][mask]\
            *self.m.par['intercept'][mask]
        
        [dwetnew, ddissnew] = _do_jolliet(wa,dwetairveg[mask],
                                          ddissairveg[mask],twet,tdry,tsum)
        dwetairveg[mask]=dwetnew
        ddissairveg[mask]=ddissnew
        
        ##air-freshwater
        dwetairfw=copy.copy(self.D[(2,4,'betr_air2_freshwater_wetparticle')])
        ddissairfw=copy.copy(self.D[(2,4,'betr_air2_freshwater_dissolution')])
        mask=where((self.m.par['stdry'] != 0) & (self.m.par['stwet'] != 0)
                   & (dwetairfw != 0) & (ddissairfw != 0))
        tdry=self.m.par['stdry'][mask]
        twet=self.m.par['stwet'][mask]
        tsum=tdry+twet
        wa=self.m.vdict[2]['bulk'][mask]*self.m.zdict[2]['bulk'][mask]\
            *2/tdry*self.m.par['perc4'][mask]
        
        [dwetnew, ddissnew] = _do_jolliet(wa,dwetairfw[mask],
                                          ddissairfw[mask],twet,tdry,tsum)
        dwetairfw[mask]=dwetnew
        ddissairfw[mask]=ddissnew

        ##air-ocean
        dwetairocean=copy.copy(self.D[(2,5,'betr_air2_ocean_wetparticle')])
        ddissairocean=copy.copy(self.D[(2,5,'betr_air2_ocean_dissolution')])
        mask=where((self.m.par['stdry'] != 0) & (self.m.par['stwet'] != 0)
                   & (dwetairocean != 0) & (ddissairocean != 0))
        tdry=self.m.par['stdry'][mask]
        twet=self.m.par['stwet'][mask]
        tsum=tdry+twet
        wa=self.m.vdict[2]['bulk'][mask]*self.m.zdict[2]['bulk'][mask]\
            *2/tdry*self.m.par['perc5'][mask]
        
        [dwetnew, ddissnew] = _do_jolliet(wa,dwetairocean[mask],
                                          ddissairocean[mask],twet,tdry,tsum)
        dwetairocean[mask]=dwetnew
        ddissairocean[mask]=ddissnew

        ##air-soil
        dwetairsoil=copy.copy(self.D[(2,6,'betr_air2_soil_wetparticle')])
        ddissairsoil=copy.copy(self.D[(2,6,'betr_air2_soil_dissolution')])
        mask=where((self.m.par['stdry'] != 0) & (self.m.par['stwet'] != 0)
                   & (dwetairsoil != 0) & (ddissairsoil != 0))
        tdry=self.m.par['stdry'][mask]
        twet=self.m.par['stwet'][mask]
        tsum=tdry+twet
        wa=self.m.vdict[2]['bulk'][mask]*self.m.zdict[2]['bulk'][mask]\
            *2/tdry*self.m.par['perc6'][mask]
        [dwetnew, ddissnew] = _do_jolliet(wa,dwetairsoil[mask],
                                          ddissairsoil[mask],twet,tdry,tsum)
        dwetairsoil[mask]=dwetnew
        ddissairsoil[mask]=ddissnew
        ## Correction for Vegetation Interception (BETR-VBA)
        dwetairsoil=dwetairsoil*(1-self.m.par['perc3']*self.m.par['intercept'])
        ddissairsoil=ddissairsoil*(1-self.m.par['perc3']
                                   *self.m.par['intercept'])

        return({(2,3,'betr_air2_veg_wetparticle'):dwetairveg,
                (2,3,'betr_air2_veg_dissolution'):ddissairveg,
                (2,4,'betr_air2_freshwater_wetparticle'):dwetairfw,
                (2,4,'betr_air2_freshwater_dissolution'):ddissairfw,
                (2,5,'betr_air2_ocean_wetparticle'):dwetairocean,
                (2,5,'betr_air2_ocean_dissolution'):ddissairocean,
                (2,6,'betr_air2_soil_wetparticle'):dwetairsoil,
                (2,6,'betr_air2_soil_dissolution'):ddissairsoil}
               )

################################################################################

