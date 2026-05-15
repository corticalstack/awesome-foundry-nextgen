"""
ISS Data Utilities

Handles fetching NASA Daily Reports, parsing content, and managing the known incident database.
"""
import re
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# --- Incident Database Definitions ---

class IncidentSeverity(Enum):
    """NASA-style severity classification"""
    NOMINAL = "nominal"           # Normal operations
    ADVISORY = "advisory"         # Worth noting, no action required
    CAUTION = "caution"           # Potential issue, monitoring needed
    WARNING = "warning"           # Significant issue, action may be needed
    CRITICAL = "critical"         # Serious issue requiring immediate attention

class IncidentCategory(Enum):
    """ISS system categories"""
    ECLSS = "eclss"              # Environmental Control & Life Support
    POWER = "power"              # Electrical Power System
    THERMAL = "thermal"          # Thermal Control System
    COMMS = "comms"              # Communication Systems
    GNC = "gnc"                  # Guidance, Navigation & Control
    STRUCTURE = "structure"      # Structural/Pressure issues
    EVA = "eva"                  # Spacewalk related
    CREW = "crew"                # Crew health/safety
    PAYLOAD = "payload"          # Science experiments
    SOFTWARE = "software"        # Computer/software issues
    DOCKING = "docking"          # Visiting vehicle operations

@dataclass
class ISSIncident:
    """A documented ISS incident"""
    date: str                          # YYYY-MM-DD
    title: str                         # Brief description
    category: IncidentCategory
    severity: IncidentSeverity
    description: str                   # Detailed description
    keywords: List[str]                # Key terms that might appear in reports
    resolution: Optional[str] = None   # How it was resolved
    duration_days: int = 1             # How many days the incident affected

# Known ISS incidents - verified against NASA reports
KNOWN_INCIDENTS: List[ISSIncident] = [
    ISSIncident("2024-06-24", "EVA-90 Water Leak Termination", IncidentCategory.EVA, IncidentSeverity.CAUTION, "EVA terminated due to water leak in airlock SCU.", ["water", "leak", "eva", "terminate"], duration_days=1),
    ISSIncident("2023-10-10", "Nauka Module Radiator Leak", IncidentCategory.STRUCTURE, IncidentSeverity.WARNING, "External coolant leak from Nauka backup radiator.", ["leak", "nauka", "radiator", "coolant"], duration_days=5),
    ISSIncident("2022-12-15", "Soyuz MS-22 Coolant Leak", IncidentCategory.THERMAL, IncidentSeverity.WARNING, "Significant coolant leak from Soyuz MS-22 external radiator.", ["coolant", "leak", "soyuz", "radiator"], "Crew return on MS-23", duration_days=7),
    ISSIncident("2023-02-14", "Progress MS-21 Coolant Leak", IncidentCategory.THERMAL, IncidentSeverity.WARNING, "Coolant leak detected on Progress MS-21 cargo vehicle.", ["coolant", "leak", "progress"], duration_days=2),
    ISSIncident("2022-09-29", "Roscosmos Segment Air Leak", IncidentCategory.STRUCTURE, IncidentSeverity.CAUTION, "Elevated air leak rate detected in Russian segment.", ["air leak", "pressure", "russian segment"], duration_days=14),
    ISSIncident("2021-07-29", "Nauka Module Thruster Misfire", IncidentCategory.GNC, IncidentSeverity.CRITICAL, "Nauka module thrusters fired unexpectedly after docking, tilting ISS.", ["nauka", "thruster", "attitude", "tilt"], "Attitude recovered", duration_days=2),
    ISSIncident("2020-08-21", "Zvezda Air Leak Detection", IncidentCategory.STRUCTURE, IncidentSeverity.WARNING, "Air leak localized to Zvezda service module.", ["air leak", "zvezda", "pressure"], duration_days=30),
    ISSIncident("2020-10-14", "Toilet System Failure", IncidentCategory.ECLSS, IncidentSeverity.CAUTION, "US segment toilet (WHC) malfunction.", ["toilet", "WHC", "waste"], "Repaired", duration_days=3),
    ISSIncident("2019-04-19", "Power Channel Anomaly", IncidentCategory.POWER, IncidentSeverity.CAUTION, "Sequential shunt unit (SSU) anomaly.", ["SSU", "power", "shunt"], duration_days=2),
    ISSIncident("2018-08-30", "Soyuz MS-09 Pressure Leak", IncidentCategory.STRUCTURE, IncidentSeverity.CAUTION, "Pressure leak traced to 2mm hole in Soyuz MS-09.", ["hole", "leak", "soyuz", "pressure"], "Hole sealed", duration_days=5),
    ISSIncident("2018-10-11", "Soyuz MS-10 Launch Abort", IncidentCategory.DOCKING, IncidentSeverity.CRITICAL, "Soyuz MS-10 launch aborted due to booster failure.", ["soyuz", "abort", "launch"], duration_days=1),
    ISSIncident("2017-05-23", "CDRA CO2 Scrubber Issue", IncidentCategory.ECLSS, IncidentSeverity.CAUTION, "CDRA bed swap anomaly.", ["CDRA", "CO2", "scrubber"], duration_days=4),
    ISSIncident("2016-12-01", "Progress MS-04 Launch Failure", IncidentCategory.DOCKING, IncidentSeverity.WARNING, "Progress MS-04 cargo vehicle lost during launch.", ["progress", "launch", "failure"], duration_days=1),
    ISSIncident("2015-08-24", "USOS Oxygen Generation Issue", IncidentCategory.ECLSS, IncidentSeverity.CAUTION, "OGS shutdown due to hydrogen sensor issue.", ["OGS", "oxygen", "hydrogen"], duration_days=3),
    ISSIncident("2014-12-03", "EVA Suit Water Intrusion", IncidentCategory.EVA, IncidentSeverity.CAUTION, "Investigation following water intrusion incidents.", ["EVA", "suit", "water"], duration_days=2),
    ISSIncident("2013-07-16", "EVA-23 Water Intrusion Emergency", IncidentCategory.EVA, IncidentSeverity.CRITICAL, "Spacewalk terminated early due to water in helmet.", ["EVA", "water", "helmet", "abort"], "EVA terminated", duration_days=1),
    ISSIncident("2013-05-09", "Ammonia Leak False Alarm", IncidentCategory.THERMAL, IncidentSeverity.WARNING, "Crew sheltered due to possible ammonia leak (false alarm).", ["ammonia", "leak", "shelter"], duration_days=1),
]

KNOWN_NORMAL_DATES = [
    "2024-03-15", "2024-01-22", "2023-09-18", "2023-06-05", "2023-03-27", 
    "2022-11-14", "2022-07-11", "2022-04-04", "2021-10-18", "2021-05-24", 
    "2020-03-16", "2019-08-12", "2019-02-27", "2018-05-14", "2017-09-11", 
    "2016-07-18", "2015-04-20", "2014-03-10"
]

def get_evaluation_dataset() -> List[Dict]:
    """Mix incidents and normal days for evaluation."""
    dataset = []
    for incident in KNOWN_INCIDENTS:
        dataset.append({
            "date": incident.date,
            "expected_severity": incident.severity.value,
            "expected_category": incident.category.value,
            "is_incident": True,
            "title": incident.title,
            "description": incident.description
        })
    for date in KNOWN_NORMAL_DATES:
        dataset.append({
            "date": date,
            "expected_severity": IncidentSeverity.NOMINAL.value,
            "expected_category": None,
            "is_incident": False,
            "title": "Normal Operations",
            "description": "Routine ISS operations"
        })
    return sorted(dataset, key=lambda x: x["date"])

# --- Report Fetching & Parsing ---

DATA_START_DATE = "2013-03-01"
DATA_END_DATE = "2024-07-29"

def _fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (ISS-Analysis)'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except:
        return None

def _build_nasa_urls(date: str) -> List[str]:
    """Handle NASA's inconsistent URL formatting over the years."""
    dt = datetime.strptime(date, "%Y-%m-%d")
    y, m, d = dt.year, dt.month, dt.day
    y_2d = y % 100
    
    return [
        f"https://www.nasa.gov/blogs/stationreport/{y}/{m:02d}/{d:02d}/iss-daily-summary-report-{m}-{d:02d}-{y}/",
        f"https://www.nasa.gov/blogs/stationreport/{y}/{m:02d}/{d:02d}/iss-daily-summary-report-{m}-{d}-{y}/",
        f"https://www.nasa.gov/blogs/stationreport/{y}/{m:02d}/{d:02d}/iss-daily-summary-report-{m:02d}-{d:02d}-{y_2d:02d}/",
        f"https://www.nasa.gov/blogs/stationreport/{y}/{m:02d}/{d:02d}/iss-daily-summary-report-{m:02d}-{d:02d}-{y}/",
        f"https://www.nasa.gov/blogs/stationreport/{y}/{m}/{d}/iss-daily-summary-report-{m:02d}-{d:02d}-{y_2d:02d}/"
    ]

def _parse_report_content(html: str) -> str:
    """Extract the main report text from NASA blog HTML."""
    # Find main content using regex
    content_match = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL | re.IGNORECASE) or \
                    re.search(r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
    
    text = content_match.group(1) if content_match else html

    # Clean HTML tags
    text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '\n', text)
    text = re.sub(r'\n+', '\n', text).strip()
    
    # HTML entities
    replacements = {'&amp;': '&', '&nbsp;': ' ', '&#8211;': '-', '&#8217;': "'", '&rsquo;': "'"}
    for k, v in replacements.items():
        text = text.replace(k, v)
        
    # Trim to actual report content
    # Note: We do NOT want to skip the intro paragraph as it often contains the major headlines
    # markers = ['Payloads', 'ISS Daily Summary', 'Three-Expedition', 'Systems:']
    start = 0
        
    end_markers = ['More from ISS', 'Share on', 'Posted by']
    end = len(text)
    for m in end_markers:
        idx = text.find(m, start)
        if idx != -1 and idx < end:
            end = idx
            
    return text[:end].strip()

def fetch_report(date: str) -> Dict:
    """Fetch report for a date. Returns dict with 'success', 'report_text'."""
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        if dt < datetime.strptime(DATA_START_DATE, "%Y-%m-%d") or dt > datetime.strptime(DATA_END_DATE, "%Y-%m-%d"):
            return {"success": False, "error": "Date out of range"}
    except ValueError:
        return {"success": False, "error": "Invalid date"}

    for url in _build_nasa_urls(date):
        html = _fetch_url(url) or _fetch_url(url.rstrip('/'))
        if html:
            text = _parse_report_content(html)
            if len(text) > 100 and "Skip to main content" not in text[:200]:
                return {"success": True, "date": date, "report_text": text[:6000]}
    
    return {"success": False, "error": "Report not found"}

# --- LLM Prompts & Formatting ---

def create_classification_prompt(report_text: str) -> Dict:
    """Create system/user prompts for classification."""
    system = """You are an expert ISS Flight Controller. Your primary job is to classify the daily station status report into exactly one severity level.

SEVERITY DEFINITIONS (Highest to Lowest):

1. CRITICAL
   - Immediate threat to Crew Safety or Vehicle Integrity.
   - VISITING VEHICLE: Manned Launch Abort/Failure is CRITICAL.
   - GNC: Unplanned Thruster Firing / Loss of Attitude Control is CRITICAL.
   - EVA: Termination due to safety/failure is CRITICAL.
   - Examples: Fire, Rapid Depressurization, Toxic Atmosphere.

2. WARNING
   - Loss of a critical system function or redundancy.
   - VISITING VEHICLE: Cargo Launch Abort/Failure is WARNING.
   - LEAKS: External Coolant/Ammonia Leaks are WARNING. Air/Pressure Leaks are WARNING (unless rapid/toxic).
   - Examples: Loss of primary power bus, partial loss of life support.

3. CAUTION
   - Degraded component performance or localized failure.
   - Examples: Sensor failure, minor water leak, RPCM trip, component overheating, software crash.

4. ADVISORY
   - Minor off-nominal condition with no impact.
   - Examples: Sensor glitch, inventory issue.

5. NOMINAL
   - Normal operations.
   - MAINTENANCE: Replacement of failed parts (R&R) is NOMINAL if successful and redundancy was maintained.
   - PAYLOADS: Aborts/Troubleshooting on Science Payloads are NOMINAL/ADVISORY.

Step-by-Step Analysis Rules:
1. Scan for key terms: Leak, Abort, Fail, Trip, Off-Nominal.
2. Determine if the event was PLANNED (Nominal) or UNPLANNED.
3. Assess impact. Use the Definitions above strictly.
   - If a Component Failed but was Fixed immediately -> Nominal/Advisory.
   - If Cargo Launch Failed -> Warning.
   - If Crew Launch Failed -> Critical.

Strict Output Format:
SEVERITY: <nominal, advisory, caution, warning, or critical>
CATEGORY: <eclss, power, thermal, structure, gnc, eva, comms, software, payload, or none>
SUMMARY: <1 sentence summary>
REASONING: <Explain clearly why this severity was chosen over others>"""

    user = f"Analyze this ISS Daily Summary Report:\n\n{report_text[:6000]}"
    return {"system": system, "user": user}

def parse_classification_response(response: str) -> Dict:
    """Parse text response into structured dict."""
    result = {"severity": "unknown", "category": "unknown", "summary": "", "reasoning": ""}
    
    start_map = {"SEVERITY:": "severity", "CATEGORY:": "category", "SUMMARY:": "summary", "REASONING:": "reasoning"}
    
    for line in response.split('\n'):
        for key, field in start_map.items():
            if line.upper().startswith(key):
                result[field] = line[len(key):].strip().lower() if field in ['severity', 'category'] else line[len(key):].strip()
                
    # Regex fallbacks if simple parsing failed
    if result["severity"] == "unknown":
        m = re.search(r'SEVERITY:\s*(\w+)', response, re.IGNORECASE)
        if m: result["severity"] = m.group(1).lower()
        
    return result

def evaluate_classification(pred: Dict, ground_truth: Dict) -> Dict:
    """Compare prediction to ground truth."""
    p_sev = pred.get("severity", "unknown")
    e_sev = ground_truth["expected_severity"]
    
    exact = p_sev == e_sev
    
    # Severity closeness
    levels = ["nominal", "advisory", "caution", "warning", "critical"]
    try:
        p_idx = levels.index(p_sev)
        e_idx = levels.index(e_sev)
        close = abs(p_idx - e_idx) <= 1
    except:
        close = False
        
    return {
        "severity_exact_match": exact,
        "severity_close_match": close,
        "is_incident": ground_truth["is_incident"],
        "incident_detected": p_sev not in ["nominal", "unknown", "advisory"] if ground_truth["is_incident"] else p_sev not in ["nominal", "unknown"],
        "predicted_severity": p_sev,
        "expected_severity": e_sev
    }

def create_training_example(report: Dict, ground_truth: Dict) -> Dict:
    """
    Create a training example for fine-tuning.
    
    Args:
        report: Fetched report dict with 'report_text', 'date', etc.
        ground_truth: Dict with 'expected_severity', 'expected_category', etc.
    
    Returns:
        Dict in messages format for fine-tuning.
    """
    prompts = create_classification_prompt(report["report_text"])
    
    # Create the expected response
    severity = ground_truth["expected_severity"]
    category = ground_truth.get("expected_category") or "none"
    title = ground_truth.get("title", "")
    description = ground_truth.get("description", "")
    
    if severity == "nominal":
        summary = "Normal ISS operations with routine maintenance and science activities."
        reasoning = "No anomalies, failures, or concerns mentioned. Standard payload operations and crew activities."
    else:
        summary = title if title else f"{severity.upper()} condition detected."
        reasoning = description if description else f"Report contains indicators of {severity} level concerns."
    
    expected_response = f"""SEVERITY: {severity}
CATEGORY: {category}
SUMMARY: {summary}
REASONING: {reasoning}"""

    return {
        "messages": [
            {"role": "system", "content": prompts["system"]},
            {"role": "user", "content": prompts["user"]},
            {"role": "assistant", "content": expected_response}
        ],
        "metadata": {
            "date": report.get("date"),
            "ground_truth_severity": severity,
            "ground_truth_category": category
        }
    }


# --- Synthetic Data Generation ---

SYNTHETIC_REPORT_PROMPT = """You are a NASA ISS Daily Summary Report writer. Generate a realistic ISS Daily Summary Report for a {severity} day.

SEVERITY LEVEL: {severity}
CATEGORY: {category}
SCENARIO: {scenario}

Write a detailed report (300-500 words) in the exact style of NASA ISS Daily Summary Reports. Include:
- Payloads section with 2-3 science experiments
- Systems section with the main event matching the severity/category
- Use realistic ISS terminology, crew names, module names (Node 1, Columbus, Destiny, Zvezda, etc.)
- Include specific technical details (valve names, sensor readings, timestamps)

For NOMINAL reports: Focus on routine science, maintenance, and crew activities.
For CAUTION/WARNING/CRITICAL: Include the specific anomaly/failure matching the scenario.

Output ONLY the report text, no headers or explanations."""

SYNTHETIC_SCENARIOS = [
    # NOMINAL scenarios (50%)
    {"severity": "nominal", "category": "none", "scenario": "Routine science day with multiple payload operations"},
    {"severity": "nominal", "category": "none", "scenario": "Cargo transfer operations from visiting vehicle"},
    {"severity": "nominal", "category": "none", "scenario": "Crew health assessments and exercise"},
    {"severity": "nominal", "category": "none", "scenario": "EVA preparation activities and tool configuration"},
    {"severity": "nominal", "category": "none", "scenario": "Successful docking of cargo vehicle"},
    {"severity": "nominal", "category": "none", "scenario": "Robotic arm operations for payload installation"},
    {"severity": "nominal", "category": "none", "scenario": "Routine maintenance and filter replacements"},
    {"severity": "nominal", "category": "none", "scenario": "Educational downlink and media events"},
    {"severity": "nominal", "category": "none", "scenario": "Crew handover activities between expeditions"},
    {"severity": "nominal", "category": "none", "scenario": "Successful completion of multi-day experiment"},
    # ADVISORY scenarios (10%)
    {"severity": "advisory", "category": "payload", "scenario": "Minor science payload data anomaly, under investigation"},
    {"severity": "advisory", "category": "comms", "scenario": "Brief communication dropout, quickly recovered"},
    # CAUTION scenarios (20%)
    {"severity": "caution", "category": "eclss", "scenario": "CDRA CO2 scrubber requiring troubleshooting"},
    {"severity": "caution", "category": "power", "scenario": "RPCM trip on non-critical circuit"},
    {"severity": "caution", "category": "thermal", "scenario": "Elevated temperature on pump module"},
    {"severity": "caution", "category": "structure", "scenario": "Minor pressure variance requiring monitoring"},
    {"severity": "caution", "category": "software", "scenario": "MDM requiring reboot after software fault"},
    {"severity": "caution", "category": "eclss", "scenario": "WHC toilet system malfunction"},
    # WARNING scenarios (15%)
    {"severity": "warning", "category": "thermal", "scenario": "External coolant leak detected on visiting vehicle"},
    {"severity": "warning", "category": "structure", "scenario": "Elevated air leak rate localized to module"},
    {"severity": "warning", "category": "docking", "scenario": "Cargo vehicle launch failure"},
    {"severity": "warning", "category": "power", "scenario": "Loss of power channel requiring load shedding"},
    # CRITICAL scenarios (5%)
    {"severity": "critical", "category": "eva", "scenario": "EVA terminated early due to suit malfunction"},
    {"severity": "critical", "category": "gnc", "scenario": "Unplanned thruster firing causing attitude excursion"},
    {"severity": "critical", "category": "docking", "scenario": "Crew vehicle launch abort"},
]

def get_synthetic_scenarios(count: int = 500) -> List[Dict]:
    """Generate a list of scenarios for synthetic data generation."""
    import random
    scenarios = []
    
    # Weight distribution: 50% nominal, 10% advisory, 20% caution, 15% warning, 5% critical
    weights = {
        "nominal": 0.50,
        "advisory": 0.10,
        "caution": 0.20,
        "warning": 0.15,
        "critical": 0.05
    }
    
    severity_scenarios = {}
    for s in SYNTHETIC_SCENARIOS:
        sev = s["severity"]
        if sev not in severity_scenarios:
            severity_scenarios[sev] = []
        severity_scenarios[sev].append(s)
    
    for _ in range(count):
        # Pick severity based on weights
        r = random.random()
        cumulative = 0
        chosen_severity = "nominal"
        for sev, weight in weights.items():
            cumulative += weight
            if r <= cumulative:
                chosen_severity = sev
                break
        
        # Pick random scenario for that severity
        if chosen_severity in severity_scenarios:
            scenario = random.choice(severity_scenarios[chosen_severity])
            scenarios.append(scenario.copy())
        else:
            scenarios.append({"severity": "nominal", "category": "none", "scenario": "Routine operations"})
    
    return scenarios

def create_synthetic_report_prompt(scenario: Dict) -> Dict:
    """Create prompt for generating a synthetic ISS report."""
    return {
        "system": "You are an expert NASA technical writer who creates ISS Daily Summary Reports.",
        "user": SYNTHETIC_REPORT_PROMPT.format(**scenario)
    }
