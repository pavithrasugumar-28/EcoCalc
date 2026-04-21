# EcoCalc

**Cinematic Carbon Emission Calculator for Sustainable Living in India**

India Carbon Tracker is a modular carbon emission tracking application designed to estimate and visualize daily CO₂ emissions using India-specific activity patterns. The system combines immersive UI design with structured emission logic to promote sustainability awareness.

\---

# Overview

EcoCalc: India Carbon Tracker transforms conventional carbon calculators into an interactive experience. Users navigate through a cinematic interface—from Earth visualization to localized Indian activity inputs—culminating in emission analysis and sustainability recommendations.

The system is designed with scalability, usability, and environmental accuracy in mind.

\---

# Key Features

**Cinematic User Experience**  
Structured transitions guide users through a visual journey:
Loading → Earth View → India Focus → Login → Dashboard → Activity Input → Results

**India-Specific Emission Modeling**  
Calculations reflect realistic patterns including transport, electricity usage, and daily activities.

**Interactive Dashboard**  
Displays emission summaries and activity insights.

**Recommendation Engine**  
Generates rule-based sustainability suggestions.

**Persistent Storage**  
SQLite-based storage maintains user data and emission history.

\---

# Technology Stack

|Component|Technology|
|-|-|
|Language|Python|
|GUI Framework|Tkinter|
|Database|SQLite|
|Architecture|Modular MVC-style|
|UI Rendering|Canvas Animations|
|Logic Engine|Rule-Based Processing|

\---

# Project Structure

carbon\_calculator/

├── app.py  
├── main.py

├── db/  
│   └── setup.py

├── engine/  
│   └── emission\_calculator.py

├── recommendation/  
│   └── rule\_engine.py

├── ui/  
│   ├── splash\_screen.py  
│   ├── earth\_screen.py  
│   ├── india\_screen.py  
│   ├── login\_screen.py  
│   ├── dashboard\_screen.py  
│   ├── activity\_form.py  
│   ├── animations.py  
│   ├── theme.py  
│   └── assets\_loader.py

├── india\_carbon\_emissions.db

\---

# Installation

Clone the repository:

git clone (https://github.com/pavithrasugumar-28/EcoCalc)

Navigate to project:

cd EcoCalc/carbon_calculator

Run the application:

python app.py

\---

# Usage

1. Launch the application
2. Navigate through cinematic startup
3. Login or create profile
4. Enter activity data
5. View emission results
6. Review sustainability recommendations

\---

# Emission Model

CO₂ Emission = Activity Value × Emission Factor

Factors are configurable and designed to reflect realistic Indian usage patterns.

\---

# Future Enhancements

* Web-based deployment
* Mobile application version
* Cloud database integration
* AI-based emission prediction
* Advanced dashboards
* GPS-based tracking

\---

# Author

**Pavithra Sugumar**  
Developer | Innovative Solutions Builder

\---

# License

This project is licensed under the MIT License.

