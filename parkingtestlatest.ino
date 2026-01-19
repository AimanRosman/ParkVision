#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include "WiFi.h"
#include "HTTPClient.h"
#include <PubSubClient.h>

// WiFi and MQTT Settings
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* host = "YOUR_SERVER_IP"; // Change this to your localhost IP address
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* mqtt_client_id = "DHT11_topic_manros";
const char* dht_topic = "DHT11_topic_manros";
const char* dht_topic1 = "DHT11_topic1_manros";

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// IR sensor and LED pins
#define IR_CAR1 32
#define IR_CAR2 35
#define IR_CAR3 27
#define R_LED_PIN 18
#define G_LED_PIN 19
#define B_LED_PIN 4

short irSensorPins[3] = {IR_CAR1, IR_CAR2, IR_CAR3};
short ledPins[3] = {R_LED_PIN, G_LED_PIN, B_LED_PIN};

LiquidCrystal_I2C lcd(0x27, 21, 22); // LCD screen settings
DHT dht(25, DHT11); // DHT11 sensor settings

// MQ2 gas sensor and relay pin setup
const int mq2Pin = 34;      // MQ2 sensor connected to A2
const int relayPin = 14;    // Relay control pin connected to D7
const int threshold = 1000;  // Set threshold for gas detection

// MQTT Callback
void callback(char* topic, byte* payload, unsigned int length) {
  // Callback function for MQTT (currently unused)
}

// Reconnect to MQTT
void reconnect() {
  while (!mqttClient.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (mqttClient.connect(mqtt_client_id)) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);

  // WiFi setup
  WiFi.begin(ssid, password);
  Serial.println("Connecting...");
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(1000);
  }
  Serial.println("Connected");

  // MQTT setup
  mqttClient.setServer(mqtt_server, mqtt_port);
  mqttClient.setCallback(callback);
  reconnect();

  // Initialize IR sensor and LED pins
  for (short i = 0; i < 3; i++) {
    pinMode(irSensorPins[i], INPUT_PULLUP);
    pinMode(ledPins[i], OUTPUT);
  }

  // Initialize LCD and DHT
  lcd.init();
  lcd.backlight();
  lcd.print("Wifi Connected...");
  dht.begin();

  // Setup MQ2 sensor and relay
  pinMode(relayPin, OUTPUT);
  digitalWrite(relayPin, LOW); // Ensure the relay is off initially
  Serial.println("MQ2 Gas Sensor Setup...");
}

void loop() {
  // Check MQTT connection
  if (!mqttClient.connected()) {
    reconnect();
  }
  mqttClient.loop();

  // MQ2 Gas sensor reading
  int sensorValue = analogRead(mq2Pin);
  Serial.print("MQ2 Sensor Value: ");
  Serial.println(sensorValue);

  // Control relay based on gas detection
  if (sensorValue > threshold) {
    digitalWrite(relayPin, HIGH); // Activate relay (turn on fan)
    Serial.println("Gas detected! Relay ON, Fan ON.");
  } else {
    digitalWrite(relayPin, LOW); // Deactivate relay (turn off fan)
    Serial.println("No gas detected. Relay OFF, Fan OFF.");
  }

  // IR sensor parking slot monitoring
  String sensorStatus[3];
  int availableSlots = 3;
  for (short i = 0; i < 3; i++) {
    sensorStatus[i] = detectIRStatus(irSensorPins[i]);
    Serial.print("IR Sensor ");
    Serial.print(i + 1);
    Serial.print(": ");
    Serial.println(sensorStatus[i]);
    
    if (sensorStatus[i] == "Occupied") {
      digitalWrite(ledPins[i], LOW);
      availableSlots--;
    } else {
      digitalWrite(ledPins[i], HIGH);
    }
  }

  // Display parking and sensor status on LCD
  displayLCD(sensorStatus, availableSlots);
  readDHT(3 - availableSlots, sensorStatus, sensorValue); // Pass gas sensor value

  delay(1000);
}

// IR sensor status detection
String detectIRStatus(short sensorPin) {
  if (digitalRead(sensorPin) == LOW) {
    delay(50);
    if (digitalRead(sensorPin) == LOW) {
      return "Occupied";
    }
  }
  return "Empty";
}

// Display parking status on the LCD
void displayLCD(String sensorStatus[], int availableSlots) {
  lcd.clear();
  char slotNames[3][3] = {"A4", "A5", "A6"};
  for (int i = 2; i >= 0; i--) {
    lcd.setCursor(0, 2 - i);
    lcd.print("Slot ");
    lcd.print(slotNames[i]);
    lcd.print(": ");
    lcd.print(sensorStatus[i]);
  }
  lcd.setCursor(0, 3);
  lcd.print("Available: ");
  lcd.print(availableSlots);
}

// Read DHT11 sensor and publish data to MQTT and HTTP
void readDHT(int slots, String sensorStatus[], int gasValue) {
  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();
  
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("Failed to read from DHT sensor");
    delay(2000);
    return;
  }
  
  Serial.print("Humidity: ");
  Serial.print(humidity);
  Serial.print(" %\t");
  Serial.print("Temperature: ");
  Serial.print(temperature);
  Serial.println(" *C");

  // Publish temperature and humidity if thresholds are met
  if (temperature >= 25.0 && humidity >= 60.0) {
    if (mqttClient.connected()) {
      mqttClient.publish(dht_topic, String(temperature).c_str(), true);
      mqttClient.publish(dht_topic1, String(humidity).c_str(), true);
    } else {
      Serial.println("MQTT not connected");
    }
  }

  // HTTP Request to send sensor data
  HTTPClient http;
  String link = "http://" + String(host) + "/projectfinal/kirimdata.php?temp=" + String(temperature) + 
                "&hum=" + String(humidity) + "&gas=" + String(gasValue) + 
                "&ir1=" + String(sensorStatus[0]) + 
                "&ir2=" + String(sensorStatus[1]) + 
                "&ir3=" + String(sensorStatus[2]);
  
  http.begin(link);
  int httpCode = http.GET();

  if (httpCode != HTTP_CODE_OK) {
    Serial.println("HTTP GET request failed");
    Serial.println(httpCode);
  }

  String response = http.getString();
  Serial.println(response);
  http.end();
}
