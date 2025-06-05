import RPi.GPIO as GPIO



GPIO.setmode(GPIO.BCM)
#Board pin numbers to make sence
#if GPIO.setmode is set to BOARD it won't work becuase of different pin configurations.
#GPIO.setwarnings(False)
GPIO.setup(25, GPIO.OUT)
#making the pin output
p = GPIO.PWM(25, 1)
#configures pulse at a frequency of 1/2
#frequency, the sencond input, is in hertz



p.start(10)
#starting pulse and setting duty with input
#duty is ratio of time on or off


while True:
    freq = float(input("new frequency: "))
    p.ChangeFrequency(freq)
    
    if input("stop? y/n : ") == "y":
        break


p.stop()
#stoping the pulse
GPIO.cleanup()
#sets the pins to not be in use