# 🚧 Autonomous Pothole Detection Intelligence (PotholeAI)

An AI-powered pothole detection and smart navigation system that automatically detects potholes using computer vision and displays them on an interactive map. The goal is to improve road safety, assist drivers, and help authorities identify road damage faster.

---

## 📌 Features

- 🔍 **AI-based Pothole Detection**
  - Uses a trained YOLO model to detect potholes from images or video.

- 🗺 **Interactive Map Visualization**
  - Displays detected potholes using Leaflet.js.

- ⚠ **Pothole Warning System**
  - Alerts users about potholes ahead during navigation.

- 🗃 **Database Storage**
  - Stores pothole data including GPS coordinates, severity, and status.

- 📊 **Severity Classification**
  - Classifies potholes as:
  - Minor
  - Moderate
  - Critical

- 🔄 **Complaint Tracking**
  - Tracks pothole repair status and escalation.

---

## 🏗 Project Structure

---

## ⚙️ Tech Stack

**Artificial Intelligence**
- YOLO Object Detection

**Backend**
- Python

**Database**
- SQLite

**Frontend**
- HTML
- CSS
- JavaScript
- Leaflet.js
- Leaflet Routing Machine

---

## 🧠 How It Works

1. Road images or video frames are processed using a trained YOLO model.
2. The model detects potholes and assigns a severity level.
3. The system stores pothole details in an SQLite database.
4. Detected potholes are plotted on an interactive map using GPS coordinates.
5. Drivers receive warnings when approaching dangerous potholes.

---


---

## 🗺 Navigation Interface

Open the **map.html** file in your browser to:

- View pothole locations
- Navigate between locations
- Receive pothole alerts during travel

---

## 📊 Database Schema

The database stores the following pothole information:

- pothole_id
- detected_at
- road
- location
- gps_lat
- gps_lon
- severity
- confidence
- status

This helps track pothole detection and repair progress.

---

## 🎯 Applications

- Smart city infrastructure monitoring
- Road safety improvement
- Government road maintenance systems
- Navigation systems for safer driving

---

## 🔮 Future Improvements

- Mobile application integration
- Real-time camera detection
- Automatic complaint filing to municipal authorities
- Integration with live traffic data
- Drone-based road inspection

---

## 👨‍💻 Authors

Developed as a hackathon project focused on applying AI to improve road safety and infrastructure monitoring.

---

