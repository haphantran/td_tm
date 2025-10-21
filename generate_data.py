#!/usr/bin/env python3
"""
TD Bank Threat Modeling Metrics - Sample Data Generator
Generates realistic fake data for dashboard prototyping
"""

import csv
import json
import random
from datetime import datetime, timedelta
from typing import List, Dict
import os

# Configuration
NUM_APPLICATIONS = 75
NUM_THREAT_MODELERS = 6
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 10, 15)
DATA_DIR = "data"

# TD Bank realistic data
THREAT_MODELERS = [
    "John Smith",
    "Jane Doe",
    "Michael Johnson",
    "Sarah Williams",
    "Robert Brown",
    "Emily Davis"
]

APP_CATEGORIES = [
    "Digital Banking",
    "Core Banking",
    "Trading Platform",
    "Risk Management",
    "Customer Portal",
    "Payment Processing",
    "Mobile Banking",
    "Data Analytics",
    "Wealth Management",
    "Internal Tools"
]

RISK_RATINGS = ["VH", "H", "M", "L"]
RISK_WEIGHTS = [0.25, 0.35, 0.30, 0.10]  # Distribution - More VH apps

TM_STATES = ["Completed", "In Progress", "Assigned", "Request", "Backlog"]
STATE_WEIGHTS = [0.60, 0.15, 0.10, 0.08, 0.07]  # More completions

THREAT_TYPES = [
    "Authentication Bypass",
    "SQL Injection",
    "Cross-Site Scripting (XSS)",
    "Insecure Data Storage",
    "Broken Access Control",
    "Security Misconfiguration",
    "Sensitive Data Exposure",
    "API Security Issues",
    "Insufficient Logging",
    "Cryptographic Failures"
]

MITIGATION_STATUS = ["Mitigated", "In Progress", "Open", "Accepted Risk", "Exception"]

SECURITY_REQUIREMENTS = [
    "SR-001: Multi-Factor Authentication Required",
    "SR-002: Data Encryption at Rest",
    "SR-003: Data Encryption in Transit",
    "SR-004: Input Validation and Sanitization",
    "SR-005: Secure Session Management",
    "SR-006: Access Control and Authorization",
    "SR-007: Audit Logging and Monitoring",
    "SR-008: Secure API Authentication",
    "SR-009: Password Complexity Requirements",
    "SR-010: Security Patch Management",
    "SR-011: Data Backup and Recovery",
    "SR-012: Security Testing Requirements",
    "SR-013: Secure Configuration Management",
    "SR-014: Third-Party Security Assessment",
    "SR-015: Incident Response Procedures"
]

MITIGATION_TYPES = [
    "Implement Multi-Factor Authentication",
    "Enable Database Encryption",
    "Configure TLS/SSL Encryption",
    "Add Input Validation Framework",
    "Implement Rate Limiting",
    "Update Access Control Lists",
    "Enable Security Logging",
    "Deploy Web Application Firewall",
    "Implement Security Headers",
    "Apply Security Patches",
    "Configure Network Segmentation",
    "Enable Intrusion Detection",
    "Implement Data Masking",
    "Deploy API Gateway",
    "Configure SIEM Integration"
]


def random_date(start, end):
    """Generate a random datetime between start and end dates"""
    delta = end - start
    random_days = random.randint(0, delta.days)
    return start + timedelta(days=random_days)


def generate_applications() -> List[Dict]:
    """Generate application data"""
    applications = []

    for i in range(1, NUM_APPLICATIONS + 1):
        risk_rating = random.choices(RISK_RATINGS, weights=RISK_WEIGHTS)[0]
        category = random.choice(APP_CATEGORIES)

        app = {
            "app_id": f"APP-{i:04d}",
            "app_name": f"{category} System {i}",
            "category": category,
            "risk_rating": risk_rating,
            "business_owner": f"{random.choice(['John', 'Jane', 'Bob', 'Alice', 'Tom', 'Lisa'])} {random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Davis', 'Miller'])}",
            "in_scope": random.choice([True, True, True, False])  # 75% in scope
        }
        applications.append(app)

    return applications


def generate_threat_models(applications: List[Dict]) -> List[Dict]:
    """Generate threat model records"""
    threat_models = []
    tm_id = 1

    for app in applications:
        # Most apps have 1 threat model, some have multiple versions
        num_tms = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]

        for version in range(1, num_tms + 1):
            state = random.choices(TM_STATES, weights=STATE_WEIGHTS)[0]

            # Generate realistic dates based on state
            # 30% chance of recent intake (in October 2025)
            if random.random() < 0.30:
                request_date = random_date(datetime(2025, 10, 1), END_DATE)
            else:
                request_date = random_date(START_DATE, END_DATE - timedelta(days=90))

            assigned_date = None
            start_date = None
            completed_date = None

            if state != "Request" and state != "Backlog":
                assigned_date = request_date + timedelta(days=random.randint(1, 14))

                if state != "Assigned":
                    start_date = assigned_date + timedelta(days=random.randint(0, 7))

                    if state == "Completed":
                        # Completion time varies by risk rating
                        if app["risk_rating"] == "VH":
                            days_to_complete = random.randint(15, 45)
                        elif app["risk_rating"] == "H":
                            days_to_complete = random.randint(10, 35)
                        else:
                            days_to_complete = random.randint(7, 25)

                        completed_date = start_date + timedelta(days=days_to_complete)

            # Number of threats found
            if state == "Completed":
                num_threats = random.randint(5, 25)
            elif state == "In Progress":
                num_threats = random.randint(2, 15)
            else:
                num_threats = 0

            tm = {
                "tm_id": f"TM-{tm_id:05d}",
                "app_id": app["app_id"],
                "app_name": app["app_name"],
                "risk_rating": app["risk_rating"],
                "category": app["category"],
                "version": version,
                "state": state,
                "threat_modeler": random.choice(THREAT_MODELERS),
                "request_date": request_date.strftime("%Y-%m-%d"),
                "assigned_date": assigned_date.strftime("%Y-%m-%d") if assigned_date else None,
                "start_date": start_date.strftime("%Y-%m-%d") if start_date else None,
                "completed_date": completed_date.strftime("%Y-%m-%d") if completed_date else None,
                "num_threats_identified": num_threats,
                "num_threats_mitigated": random.randint(int(num_threats * 0.6), num_threats) if num_threats > 0 else 0,
                "num_open_items": random.randint(0, 8) if state == "Completed" else 0,
                "has_pentest": random.choice([True, False]) if state == "Completed" else False,
                "pentest_gaps": random.randint(0, 3) if state == "Completed" and random.random() > 0.7 else 0
            }

            # Calculate metrics
            if tm["completed_date"] and tm["request_date"]:
                req_date = datetime.strptime(tm["request_date"], "%Y-%m-%d")
                comp_date = datetime.strptime(tm["completed_date"], "%Y-%m-%d")
                tm["days_request_to_completed"] = (comp_date - req_date).days
            else:
                tm["days_request_to_completed"] = None

            if tm["completed_date"] and tm["assigned_date"]:
                asn_date = datetime.strptime(tm["assigned_date"], "%Y-%m-%d")
                comp_date = datetime.strptime(tm["completed_date"], "%Y-%m-%d")
                tm["days_assigned_to_completed"] = (comp_date - asn_date).days
            else:
                tm["days_assigned_to_completed"] = None

            threat_models.append(tm)
            tm_id += 1

    return threat_models


def generate_threats(threat_models: List[Dict]) -> List[Dict]:
    """Generate individual threat records"""
    threats = []
    threat_id = 1

    for tm in threat_models:
        if tm["num_threats_identified"] > 0:
            for i in range(tm["num_threats_identified"]):
                status = random.choices(MITIGATION_STATUS, weights=[0.65, 0.15, 0.10, 0.07, 0.03])[0]

                threat = {
                    "threat_id": f"THR-{threat_id:06d}",
                    "tm_id": tm["tm_id"],
                    "app_id": tm["app_id"],
                    "app_name": tm["app_name"],
                    "risk_rating": tm["risk_rating"],
                    "threat_modeler": tm["threat_modeler"],
                    "threat_type": random.choice(THREAT_TYPES),
                    "severity": random.choices(["Critical", "High", "Medium", "Low"],
                                              weights=[0.1, 0.3, 0.4, 0.2])[0],
                    "status": status,
                    "security_requirement": random.choice(SECURITY_REQUIREMENTS),
                    "mitigation_type": random.choice(MITIGATION_TYPES) if status in ["Mitigated", "In Progress"] else None,
                    "identified_date": tm["completed_date"] if tm["completed_date"] else tm["start_date"],
                    "target_remediation_date": None,
                    "actual_remediation_date": None
                }

                # Set remediation dates for mitigated threats
                if threat["status"] == "Mitigated" and threat["identified_date"]:
                    ident_date = datetime.strptime(threat["identified_date"], "%Y-%m-%d")
                    days_to_remediate = random.randint(7, 90)
                    threat["target_remediation_date"] = (ident_date + timedelta(days=30)).strftime("%Y-%m-%d")
                    threat["actual_remediation_date"] = (ident_date + timedelta(days=days_to_remediate)).strftime("%Y-%m-%d")

                threats.append(threat)
                threat_id += 1

    return threats


def generate_time_series(threat_models: List[Dict]) -> List[Dict]:
    """Generate monthly aggregated metrics for time series charts"""
    monthly_data = {}

    for tm in threat_models:
        if tm["completed_date"]:
            month_key = tm["completed_date"][:7]  # YYYY-MM

            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    "month": month_key,
                    "completed_count": 0,
                    "vh_completed": 0,
                    "h_completed": 0,
                    "m_completed": 0,
                    "l_completed": 0,
                    "total_threats_identified": 0,
                    "total_threats_mitigated": 0,
                    "avg_completion_days": []
                }

            monthly_data[month_key]["completed_count"] += 1
            monthly_data[month_key][f"{tm['risk_rating'].lower()}_completed"] += 1
            monthly_data[month_key]["total_threats_identified"] += tm["num_threats_identified"]
            monthly_data[month_key]["total_threats_mitigated"] += tm["num_threats_mitigated"]

            if tm["days_request_to_completed"]:
                monthly_data[month_key]["avg_completion_days"].append(tm["days_request_to_completed"])

        # Count intakes (requests)
        month_key = tm["request_date"][:7]
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                "month": month_key,
                "completed_count": 0,
                "vh_completed": 0,
                "h_completed": 0,
                "m_completed": 0,
                "l_completed": 0,
                "total_threats_identified": 0,
                "total_threats_mitigated": 0,
                "avg_completion_days": [],
                "intake_count": 0
            }

        if "intake_count" not in monthly_data[month_key]:
            monthly_data[month_key]["intake_count"] = 0
        monthly_data[month_key]["intake_count"] += 1

    # Calculate averages and format
    time_series = []
    for month_key in sorted(monthly_data.keys()):
        data = monthly_data[month_key]

        if data["avg_completion_days"]:
            data["avg_completion_days"] = round(sum(data["avg_completion_days"]) / len(data["avg_completion_days"]), 1)
        else:
            data["avg_completion_days"] = None

        if data["total_threats_identified"] > 0:
            data["mitigation_rate"] = round((data["total_threats_mitigated"] / data["total_threats_identified"]) * 100, 1)
        else:
            data["mitigation_rate"] = None

        time_series.append(data)

    return time_series


def save_data():
    """Generate and save all data files"""
    os.makedirs(DATA_DIR, exist_ok=True)

    print("Generating applications...")
    applications = generate_applications()

    print("Generating threat models...")
    threat_models = generate_threat_models(applications)

    print("Generating threats...")
    threats = generate_threats(threat_models)

    print("Generating time series data...")
    time_series = generate_time_series(threat_models)

    # Save as CSV
    print(f"Saving to {DATA_DIR}/...")

    with open(f"{DATA_DIR}/applications.csv", "w", newline="") as f:
        if applications:
            writer = csv.DictWriter(f, fieldnames=applications[0].keys())
            writer.writeheader()
            writer.writerows(applications)

    with open(f"{DATA_DIR}/threat_models.csv", "w", newline="") as f:
        if threat_models:
            writer = csv.DictWriter(f, fieldnames=threat_models[0].keys())
            writer.writeheader()
            writer.writerows(threat_models)

    with open(f"{DATA_DIR}/threats.csv", "w", newline="") as f:
        if threats:
            writer = csv.DictWriter(f, fieldnames=threats[0].keys())
            writer.writeheader()
            writer.writerows(threats)

    with open(f"{DATA_DIR}/monthly_metrics.csv", "w", newline="") as f:
        if time_series:
            writer = csv.DictWriter(f, fieldnames=time_series[0].keys())
            writer.writeheader()
            writer.writerows(time_series)

    # Save as JSON for easier JavaScript consumption
    with open(f"{DATA_DIR}/dashboard_data.json", "w") as f:
        json.dump({
            "applications": applications,
            "threat_models": threat_models,
            "threats": threats,
            "monthly_metrics": time_series
        }, f, indent=2)

    print(f"\nData generation complete!")
    print(f"  Applications: {len(applications)}")
    print(f"  Threat Models: {len(threat_models)}")
    print(f"  Threats: {len(threats)}")
    print(f"  Monthly Records: {len(time_series)}")
    print(f"\nFiles created in '{DATA_DIR}/' directory")


if __name__ == "__main__":
    save_data()
