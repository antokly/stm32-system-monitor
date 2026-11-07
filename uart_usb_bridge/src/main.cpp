#include <Arduino.h>

// Gateway UART pins
#define RX_PIN 20
#define TX_PIN 21
#define BAUDRATE   115200

HardwareSerial GatewayUART(1); // use UART1

void setup() {
  // Native USB CDC — this is what appears as /dev/ttyACM0 or COMx on the PC
  Serial.begin(115200);

  // The UART side you're bridging to/from (sensor, MCU, modem, etc.)
  GatewayUART.begin(BAUDRATE, SERIAL_8N1, RX_PIN, TX_PIN);
}

void loop() {
  
  // UART -> USB
  while (GatewayUART.available()) {
    int c = GatewayUART.read();
    Serial.write((uint8_t)c);
  }

  // USB -> UART
  while (Serial.available()) {
    int c = Serial.read();
    GatewayUART.write((uint8_t)c);
  }
}
