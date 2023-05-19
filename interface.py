###
from threading import Timer
import serial
import sys

#graphic interface
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton,
                               QVBoxLayout, QHBoxLayout, QWidget,
                               QSlider,QDoubleSpinBox,QCheckBox)
#from __feature__ import 
##
debug=0b1
##type of widget definition
SLIDER=0
BUTTON_BOOL=1
BUTTON_PUSH=2

###define slider combined with spinbox
class mQSlider(QHBoxLayout):

    a=1
    sliderMoved = Signal(float)

    def __init__(self):
        super().__init__()
        self.slider = QSlider()
        self.box = QDoubleSpinBox()
        self.addWidget(self.box)
        self.addWidget(self.slider)
        self.step=1
        self.slider.sliderMoved.connect(self.OnSliderMove)
        self.box.valueChanged.connect(self.OnBoxSet)

    def setMaximum(self, value):
        self.slider.setMaximum(value*100)
        self.box.setMaximum(value)

    def setMinimum(self, value):
        self.slider.setMinimum(value*100)
        self.box.setMinimum(value)

    def setIncrements(self, value):
        #print(value*100)
        self.slider.setTickInterval(value*100)
        self.box.setSingleStep(value)
        self.step=value

    def setValue(self,value):
        self.box.setValue(value)
        self.slider.setValue(value*100)

#signal from slider
    def OnSliderMove(self,value):
        value = value/100
        value = int(value/self.step)*self.step
        self.sliderMoved.emit(value)
        self.box.setValue(value)

#signal from spinbox
    def OnBoxSet(self,value):
        self.sliderMoved.emit(value)
        self.slider.setValue(value*100)

##class to build ui elements necesary for the device
#we use the same class for every widgets
class widget():

    #method allowing to set channel before calling "specificAction" which then call "action"
    def do(self,args):
        self.setChannel(self.channel)
        self.specificAction(args)

    #for the check box
    def boolToCheck(self,value):
        if value:
            return Qt.Checked
        else:
            return Qt.Unchecked
        
    def checkToBool(self,value):
        if value == 0:
            return False
        return True
    
    @Slot(int)
    def __init__(self,label,mtype,action,layout,channel,master,args):

        self.label = label
        self.mtype = mtype
        self.action = action
        self.setChannel = master.setChannel
        self.channel=channel
        self.reportedValueWidget = QLabel("")

        self.specificAction = lambda _:_
        self.setValue = lambda _:_
        self.getValue = lambda _:_

        #define widget specifics : 
        #create,attach to layout, setup widget
        #connect a Signal to the function do, with args an array containing relevent arguments (this allow to run systematic code, such as channel choice (could add other tasks) )
        #define th lambda function specificAction to cast args to what action require in arguments
        if mtype == SLIDER:#args : [min,max,increments,decimals]
            #register to the widget list
            master.widgetList.append(self)

            entete = QHBoxLayout()
            layout.addLayout(entete)
            entete.addWidget(QLabel(self.label))
            entete.addWidget(self.reportedValueWidget)

            self.widget = mQSlider()
            self.widget.slider.setOrientation(Qt.Horizontal)
            self.widget.setMinimum(args[0])
            self.widget.setMaximum(args[1])
            self.widget.setIncrements(args[2])
            self.widget.box.setDecimals(args[3])
            self.setValue = self.widget.setValue

            self.widget.sliderMoved.connect(lambda x: self.do([x]))
            self.specificAction = lambda x: self.action(x[0])
            layout.addLayout(self.widget)

        elif mtype ==  BUTTON_BOOL:
            #register to the widget list
            master.widgetList.append(self)

            entete = QHBoxLayout()
            layout.addLayout(entete)
            entete.addWidget(QLabel(self.label))
            entete.addWidget(self.reportedValueWidget)

            self.widget = QCheckBox()
            self.setValue = lambda value:self.widget.setCheckState(self.boolToCheck(value))
            self.widget.stateChanged.connect(lambda x:self.do([x]))
            self.specificAction = lambda x: self.action(self.checkToBool(x[0]))
            layout.addWidget(self.widget)



        elif mtype == BUTTON_PUSH:
            self.widget = QPushButton(label)
            self.widget.clicked.connect(lambda : self.do([]))
            self.specificAction = lambda _:action()
            layout.addWidget(self.widget)


        


        else:
                self.widget = Qlabel("unknown widget type")
                layout.addWidget(self.widget)

#value read from the device 
    def setReportedValue(self,value):
        self.reportedValueWidget.setText("reported value : %.4f"%value)
        self.reportedValue = value

#put the value from the device to the graphical interface
    def pullReportedValue(self):
        self.setValue(self.reportedValue)

#put the value from the graphical interface to the device (usefull when a device reset occure)
    def forceUpdate(self):
        print("TODO force update")
        #TODO

###this class allow to read serial
class serialReader():
    def __init__(self,callback,serial):
        self.callback = callback
        self.serial = serial
        self.initTimer()


    def initTimer(self):
        self.timer = Timer(0.1,self.loop)
        self.timer.start()
        #print("timer starts")

    def loop(self,first=True,i=0):
        #print("timer ends")
        #print(self.serial.in_waiting)
        if self.serial.in_waiting > 0 and i<100:
            line = self.serial.readline()
            if (~first):
                self.callback(line)
            self.loop(False, i+1)
            return
        self.initTimer()
        self.serial.write(b'?')
        return



###main object
class EOM_control():

    #usefull to create the layouts and put them in a datastructure
    def putLayout(self,layout,parent,name):
        parent[1][name]=[layout(),{}]
        parent[0].addLayout( parent[1][name][0] )
        return parent[1][name][1]

    def __init__(self,com,reset=False):

        #serial
        if debug&0b1==0:
            print("oppening serial port")
            self.ser = serial.Serial(com)
            self.reader = serialReader(self.scraper,self.ser)
        else:
            self.ser = type('',(object,),{"write": lambda _,x:print("serial print : %s"%x)})()

        #to try to recover an output if nothing work (to complete)
        if reset:
            self.disable()
            self.setChannel(0)
            #prevent bug with the mute : 
            self.setMute(True)
            self.setMute(False)
        
        #UI definition
        self.widgetList = []
        self.frame = QWidget()
        self.ui = {"global" : [ QVBoxLayout(self.frame),{}]}
        self.gl = self.ui["global"][1]
        self.ch = self.putLayout(QHBoxLayout,self.ui["global"],"channels")
        self.putLayout(QVBoxLayout,self.gl["channels"],"A")
        self.putLayout(QVBoxLayout,self.gl["channels"],"B")
        #print(self.ui)
        makeChannel = lambda c,l: {
            "out" : widget("enable the output",BUTTON_BOOL,self.setEnable,l,c,self,[]),
            "freq" : widget("set the frequency",SLIDER,self.setFrequency,l,c,self,[10,15000,1,0]),
            "power" : widget("set the power",SLIDER,self.setPower,l,c,self,[-40,20,0.01,2]),
            "phase" : widget("set the phase",SLIDER,self.setPhase,l,c,self,[0,360,0.02,4]),

            }
        self.ch["A"][1] = makeChannel(0,self.ch["A"][0])
        self.ch["B"][1] = makeChannel(1,self.ch["B"][0])

        widget("pull from device",BUTTON_PUSH,self.pullFromDevice,self.ui['global'][0],0,self,[])
        widget("save to Rom",BUTTON_PUSH,self.saveInRom,self.ui['global'][0],0,self,[])
        #print(self.ui)

    #this code allow to decode information from the device(called by the serial reader)
    lookupCmd = {"f":"freq",
                 "r":"out",
                 "W":"power",
                 "~":"phase"}
    def scraper(self,line):
        line = line.decode()
        #print("new line to scrape : %s"%line)
        first = line[0]
        split=line.split()
        if self.lookupCmd.__contains__(first) and line[1]==')':
            try:
                a,b = split[-2][:-1],split[-1]
                a,b=float(a),float(b)
                cmd = self.lookupCmd[first]
                #print(cmd,a,b)
                self.ch["A"][1][cmd].setReportedValue(a)
                self.ch["B"][1][cmd].setReportedValue(b)
            except:
                print(line)
            
    #load all setting from device
    def pullFromDevice(self):
        for widget in  self.widgetList:
            widget.pullReportedValue()
    
    #push all settings to the device
    def pushToDevice(self):
        self.setChannel(0)
        #prevent bug with the mute : 
        self.setMute(True)
        self.setMute(False)
        for widget in  self.widgetList:
            widget.forceUpdate()

#definition of the serial commands to setup the device
    def setChannel(self,channel=0):
        self.ser.write(b'C%d ?'%channel)
        self.channel=0

    def saveInRom(self):
        self.ser.write(b'e ?')
        self.pullFromDevice()

    def setPhase(self,value):
        self.ser.write(b'~%.4f ?'%value)

    def setPower(self,power=-42):#power in dBm
        self.ser.write(b'W%.2f ?'%power)

    def setFrequency(self,freq=5000):
        self.ser.write(b'f%d ?'%freq)

    def setEnable(self,enable=False):
        self.ser.write(b'r%d E%d ?'%(enable,enable))

    def enable(self):
        self.setEnable(True)

    def disable(self):
        self.setEnable(False)

    def setMute(self,enable=False):
        self.ser.write(b'h%d ?'% ~enable)
###     
app = QApplication(sys.argv)
###
eom = EOM_control("/dev/ttyACM0")
#eom.setPower(15)
#eom.disable()
#eom.enable()
#eom.setFrequency(4645)
###
eom.frame.show()
sys.exit(app.exec_())
###
