import board
import busio
import adafruit_rfm9x
import adafruit_bmp280
import digitalio
import time


class Can():
    radio = None  #  Screw naming convention
    baro = None
    legs = None

    ten_alts = []
    alt = ten_alts[-1:]
    avg_alts = []

    armed = False
    flight = False
    legs = False
    apogee = False

    response = ""

    last_time = -1
    last_reading = -1 #Time of last reading transmitted to groundstation (tempreture, pressure, altitude)
    last_apogee = -1 #Time of last apogee check
    last_alt = -1 #Time of last flight start check
    last_transmit = -1 #Time of last transmit
    last_receive = -1 #time of last receive
    ###########################
    apogee_freq = 2 # Frequency of apogee check 
    alt_freq = 2 # Frequency of flight start check
    transmit_freq = 1
    receive_freq = 0.25
    
    def calibrate():
        Can.baro.sea_level_pressure = Can.baro.pressure

    def send(self,message):
        Can.radio.send(message)
    
    def receive(time=1):
        return Can.radio.receive(timeout=time)

    def connect():
        spi = busio.SPI(clock=board.GP2, MOSI=board.GP3, MISO=board.GP4)
        cs = digitalio.DigitalInOut(board.GP5)
        reset = digitalio.DigitalInOut(board.GP1)
        rfm9x = adafruit_rfm9x.RFM9x(spi, cs, reset, 433.0)
        try:
            rfm9x.send("Connected")
            print("Radio connected")
        except:
            print("Radio connection fail")
            return False

        i2c = busio.I2C(scl = board.GP15, sda = board.GP14)
        bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x76)
        try:
            x = bmp280.temperature()
            print("Baro connected")
        except:
            print("Baro connection fail")
            return False
        Can.legs = digitalio.DigitalInOut(board.GP16) # Still need to find pins for legs
        Can.radio = rfm9x
        Can.baro = bmp280

    def sync():
        for i in range (1,11):
            Can.send(f"Sync {i}")
            answer = Can.receive()
            if answer == f"Synced {i}":
                print(f"Sync {i} success")
                return True
            else:
                print(f"Sync {i} failed")
        print("Sync fail")
        return False

    def runtime():
        Can.connect()
        Can.sync()  #  Connection to groundstation
        Can.calibrate()  #Calibration of altimeter and motors

    def command(com):  # ? for requests that require an answer. ! for commands
        if com == "alt?":
            Can.response += f"|alt={Can.alt}"
        elif com == "arm!":
            Can.armed = True
            Can.response += f"|armed=True"
        elif com == "disarm!":
            Can.armed = False
            Can.response += f"|armed=False"
        elif com.split()[0] == "sea_level_pressure!":
            Can.baro.sea_level_pressure = int(com.split()[1])
            Can.response += f"|level-set"
        elif com == "legs!":
            Can.deploy_legs()
            Can.response += f"|legs=True"

    def deploy_legs():
        Can.legs.value(1)

def main():
    Can.runtime()
    # Preflight loop:     Should make it use only one loop.
    while True:
        now = time.monotonic()
        if (now >= Can.last_alt + 1 / Can.alt_freq) and (Can.armed is True):
            Can.last_alt = now
            if len(Can.ten_alts) < 10:
                Can.ten_alts.append(Can.baro.altitude)
            else:
                Can.avg_alts.append(sum(Can.ten_alts) / 10)
                Can.ten_alts.clear()
                if Can.avg_alts[-1] > 3: # If the averege altitude is 3, launch occured.
                    Can.avg_alts = Can.avg_alts[-3:] #Remove all but last 3 averages
                    Can.flight = True
                    break
        if (now >= Can.last_receive + 1 / Can.receive_freq):
            Can.last_receive = now
            command = Can.receive()
            Can.command(command)

    # Flight loop:
    while True:
        # update altitude averege
        now = time.monotonic()
        if (now >= Can.last_alt + 1 / Can.alt_freq):
            Can.last_alt = now
            if len(Can.ten_alts) < 10:
                Can.ten_alts.append(Can.baro.altitude)
            else:
                Can.avg_alts.append(sum(Can.ten_alts) / 10)
                Can.ten_alts.clear()

        if (now >= Can.last_apogee + 1 / Can.apogee_freq):
            Can.last_apogee = now
            if (Can.avg_alts[-1:] < Can.avg_alts[-2:]):
                Can.apogee = True
                Can.deploy_legs()
        
        if (now >= Can.last_time + 1):
            Can.last_time = now
            
        if (now >= Can.last_transmit + 1 / Can.transmit_freq):
            Can.send(f"{Can.alt} {Can.baro.pressure()} {Can.baro.temperature()} {Can.response}")  # parsed at other end using split
            Can.response = ""

        


                

            





