# 🌱 Automatic Irrigation System Using Rain Sensor and Soil Moisture Sensor

An IoT-based automatic irrigation system designed to monitor **soil moisture and rainfall** and automatically control a water pump. The system uses **NodeMCU ESP8266** as the main controller and **Blynk** for real-time monitoring.

## 📌 Project Overview

Traditional irrigation often requires manual monitoring and may lead to **over-irrigation, under-irrigation, and water wastage**.

This project automates the irrigation process by continuously monitoring the soil moisture level and rain condition. When the soil is dry and no rain is detected, the system automatically turns **ON the water pump**. The pump is turned **OFF** when sufficient moisture is detected or rain is detected.

## 🎯 Objectives

* 🌱 Automate the plant irrigation process
* 💧 Reduce water wastage
* 🌧️ Detect rainfall and avoid unnecessary watering
* 🌿 Monitor soil moisture levels
* 👩‍🌾 Reduce manual effort
* 📱 Provide real-time monitoring through Blynk

## ⚙️ Components Used

| Component                | Purpose                                |
| ------------------------ | -------------------------------------- |
| **NodeMCU ESP8266**      | Main controller and Wi-Fi connectivity |
| **Soil Moisture Sensor** | Measures soil moisture level           |
| **Rain Sensor**          | Detects rainfall                       |
| **Relay Module**         | Controls the water pump                |
| **Water Pump**           | Supplies water to the plants           |
| **Blynk App**            | Real-time monitoring                   |
| **Power Supply**         | Provides power to the system           |
| **Connecting Wires**     | Connects the components                |

## 🔄 Working Principle

```text
        🌱 Soil Moisture Sensor
                  │
                  ▼
           🌧️ Rain Sensor
                  │
                  ▼
          NodeMCU ESP8266
                  │
          ┌───────┴───────┐
          │               │
     Soil is Dry       Rain Detected
     & No Rain              │
          │                 ▼
          ▼             Pump OFF
       Relay
          │
          ▼
      💧 Pump ON
          │
          ▼
     Plant Irrigation
```

### Automatic Irrigation Logic

1. The **soil moisture sensor** measures the moisture level of the soil.
2. The **rain sensor** checks whether rain is detected.
3. NodeMCU ESP8266 processes the sensor readings.
4. If the soil is dry and there is no rain, the relay activates the pump.
5. The water pump supplies water to the plants.
6. When the soil reaches sufficient moisture or rain is detected, the pump is switched OFF.
7. The system can be monitored through the **Blynk App**.

## 📱 Blynk Monitoring

The Blynk platform is used for remote monitoring of the irrigation system.

The system can send information such as:

* Soil moisture level
* Watering count
* Wi-Fi signal strength
* Device heartbeat/status

## 💻 Software

* **MicroPython**
* **Thonny IDE / MicroPython-compatible environment**
* **Blynk IoT**
* **NodeMCU ESP8266**

## 📂 Project Structure

```text
Automatic-Irrigation-System/
│
├── README.md
│
├── code/
│   └── main.py
│
├── images/
│   ├── project.jpg
│   ├── circuit.jpg
│   └── blynk.jpg
│
├── circuit/
│   └── circuit_diagram.png
│
└── documentation/
    └── project_documentation.pdf
```

## 🔌 Pin Configuration

| Component            | NodeMCU Pin  |
| -------------------- | ------------ |
| Soil Moisture Sensor | A0           |
| Rain Sensor          | D5           |
| Relay Module         | D6           |
| Status LED           | Built-in LED |

## 🚀 How to Run

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/automatic-irrigation-system.git
```

### 2. Open the Code

Open:

```text
code/main.py
```

using a MicroPython-compatible IDE.

### 3. Configure Wi-Fi and Blynk

Update the following values in the code:

```python
WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
BLYNK_AUTH_TOKEN = "YOUR_BLYNK_AUTH_TOKEN"
```

### 4. Upload to NodeMCU

Upload `main.py` to the NodeMCU ESP8266 and run the program.

### 5. Monitor the System

Open the Blynk App to monitor the irrigation system and sensor information.

## ⚠️ Important Note

Do **not** upload real Wi-Fi passwords or Blynk authentication tokens to a public GitHub repository.

Use placeholders or a separate configuration file for sensitive information.

## 📊 Future Enhancements

* 📧 Email or mobile notifications
* 🌡️ Temperature and humidity monitoring
* 📈 Historical sensor-data graphs
* ☁️ Cloud-based data storage
* 🔋 Solar-powered irrigation
* 🤖 Smart irrigation based on weather data

## 👩‍💻 Project Information

**Project Title:** Automatic Irrigation System Using Rain Sensor and Soil Moisture Sensor

**Domain:** Internet of Things (IoT)

**Controller:** NodeMCU ESP8266

**Technology:** MicroPython

**Monitoring Platform:** Blynk

**Project Duration:** December 2025 – March 2026

---

⭐ **If you find this project useful, consider giving the repository a star!**
