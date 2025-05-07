import serial
from time import sleep

ser = serial.Serial('/dev/ttyS0', 9600, timeout=1)
sleep(2)

def send_freq(freq):
    ser.write(f'{freq}\n'.encode())
    print(f"Sending frequency: {freq} Hz")
    sleep(0.1)  # wait for the command to be processed

# First part: 50 to 100 by tens
for i in range(50, 110, 10):
    try:
        send_freq(i)
    except serial.SerialException as e:
        print(f"Error sending frequency {i}: {e}")

# Second part: 100 to 1,000,000 using multiples of powers of 10
base = 1000
while base <= 1_000_000:
    for multiplier in range(1, 10):  # start from 2 to avoid repeating 100
        number = multiplier * (base // 10)
        if number > 1_000_000:
            break
        try:
            send_freq(number)
        except serial.SerialException as e:
            print(f"Error sending frequency {number}: {e}")
    base *= 10

