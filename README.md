# SmartHomeSimulator

Part of our final project in DevSecOps course at Bar-Ilan
University ([Main project repository](https://github.com/NadavNV/SmartHomeConfig)). The project allows viewing and
managing different Smart home devices such as lights, water heaters, or air conditioners.

It is divided into several microservices, and this microservice simulates the behaviour of real-world devices (e.g. if a
water heater is turned on, the water temperature will rise over time.), in addition to randomly changing settings, to
simulate human interaction.

---

## Requirements

- A working [backend instance](https://github.com/NadavNV/SmartHomeBackend).
- [Python3](https://www.python.org/downloads/)

## Usage

- To run on your local machine:
    - Make sure you have python installed and a running backend instance.
    - Clone this repo:
      ```bash
      git clone https://github.com/NadavNV/SmartHomeDashboard.git
      cd SmartHomeDashboard
      ```
    - Run `pip install -r requirements.txt`.
    - Set an environment variable named `API_URL` whose value is the full address of the backend instance, including
      port
      (e.g. `http://localhost:5200`).
    - Run `python main.py`.
- To run in a Docker container:
    - Make sure you have a running backend instance and Docker engine.
    - Clone this repo.
    - Run `docker build -t <name for the image> .`.
    - Run `docker run -e "API_URL=<full backend address>" <image name>`.
