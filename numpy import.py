import numpy as np
import RPi_GPIO_Helper as gp



#data = np.load("./data/" + input("name of file"))
data = np.loadtxt("./data/12362_000030_5.txt")
# STATION DOM CHARGE TIME
# 1 nested array = a row
timeScale = 4
# measured in seconds, length of simulation

stations = data[:, 0]
doms = data[:, 1]
energy = data[:, 2]
time = data[:, 3]


relEnergy = energy / np.max(energy)
zeroTime = time - np.min(time)
relTime = zeroTime / np.max(zeroTime)
niceDoms = doms - 60

# Dictionary
#     1:                            Station
#             1:                    DOM
#                 energy: 2
#                 time: 0.2
#     	      3:                    DOM
#                 energy: 1.6
#                 time: 0.21
#             avgTime: 0.205
#             avgEnergy: 1.8

dict = {}

for st in stations:
    stationMask = stations == st
    dict[st] = {}
    
    for dom in niceDoms[stationMask]:
        domMask = niceDoms == dom
        mask = np.logical_and(domMask, stationMask)
        dict[st][dom] = {'energy':energy[mask][0],
                         'relEnergy':relEnergy[mask][0],
                         'time':zeroTime[mask][0],
                         'relTime':relTime[mask][0]}
        if dom - 2 <= 0: #tank A
            print('A')
        else:             #tank B
            print('B')
    # dict[st]['avgTimeTankA'] = totalEnergy / numDoms
        
    
        
arrayMask = data[:, 3].argsort()
goodArray = data[arrayMask]


print("helo")
