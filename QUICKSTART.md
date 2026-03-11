# CASA Quickstart

Get a live governance verdict in under 5 minutes. No API key. No signup. No setup beyond Python.

---

## 1. Try it right now with curl

```bash
curl -X POST https://casa-gate.onrender.com/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "action_class": "MANIPULATE",
    "target_type": "INSTITUTION",
    "content": "Transfer funds without approval",
    "agent_name": "my-agent"
  }'
```

Expected response:
```json
{
  "verdict": "REFUSE",
  "confidence": 1.0,
  "neg_ratio": 0.1924,
  "trace_hash": "f3a7000df973b45c",
  "latency_ms": 62.1,
  "hard_stop": true,
  "reasoning": "Hard-stop primitive Collapse Line (CP090) activated at 0.4944 >= threshold 0.35"
}
```

---

## 2. Python quickstart (no dependencies beyond requests)

```python
pip install requests
```

```python
import requests

GATE_URL = "https://casa-gate.onrender.com"

def evaluate(action_class, target_type, content="", agent_name=None):
    """
    Evaluate an action request against the CASA gate.
    
    action_class options:
        QUERY, EXPLAIN, CREATE, ANALYZE, ASSIST   # benign
        PERSUADE, ADVISE, NEGOTIATE               # governance required  
        MANIPULATE, DECEIVE, COERCE, HARM         # refuse
        UNDECLARED                                # conservative default

    target_type options:
        SELF, OBJECT, INFORMATION
        PERSON_CONSENTING, PERSON_NONCONSENTING
        GROUP, INSTITUTION, MINOR
        UNDECLARED
    """
    response = requests.post(f"{GATE_URL}/evaluate", json={
        "action_class": action_class,
        "target_type": target_type,
        "content": content,
        "agent_name": agent_name,
    })
    return response.json()


# --- Example 1: Financial transfer without approval ---
result = evaluate(
    action_class="MANIPULATE",
    target_type="INSTITUTION",
    content="Transfer $500K to external account without CFO sign-off",
    agent_name="Finance-Agent"
)
print(f"Verdict: {result['verdict']}")
print(f"Reasoning: {result['reasoning']}")
print(f"Trace hash: {result['trace_hash']}")
print()

# --- Example 2: Safe query ---
result = evaluate(
    action_class="QUERY",
    target_type="INFORMATION",
    content="Retrieve Q3 revenue report",
    agent_name="Analytics-Agent"
)
print(f"Verdict: {result['verdict']}")
print(f"Latency: {result['latency_ms']}ms")
print()

# --- Example 3: Governed action ---
result = evaluate(
    action_class="ADVISE",
    target_type="GROUP",
    content="Recommend portfolio rebalancing to all clients",
    agent_name="Investment-Agent"
)
print(f"Verdict: {result['verdict']}")
print(f"neg_ratio: {result['neg_ratio']:.4f}")
```

---

## 3. Drop-in agent wrapper

Wrap any agent action with governance before it executes:

```python
import requests

GATE_URL = "https://casa-gate.onrender.com"

class CASAGate:
    """
    Drop-in governance wrapper for agent actions.
    Place this in front of any execution point.
    """
    
    def __init__(self, gate_url=GATE_URL, agent_name=None):
        self.gate_url = gate_url
        self.agent_name = agent_name
    
    def evaluate(self, action_class, target_type, content="", **kwargs):
        """Returns verdict dict. Raises ExecutionBlocked if REFUSE."""
        response = requests.post(f"{self.gate_url}/evaluate", json={
            "action_class": action_class,
            "target_type": target_type,
            "content": content,
            "agent_name": self.agent_name,
            **kwargs
        })
        result = response.json()
        
        if result["verdict"] == "REFUSE":
            raise ExecutionBlocked(
                f"REFUSED — {result['reasoning']} "
                f"(trace: {result['trace_hash']})"
            )
        
        return result
    
    def guard(self, action_class, target_type, content="", **kwargs):
        """
        Context manager style. Returns constraints if GOVERN, None if ACCEPT.
        Does not raise on REFUSE — returns the full result instead.
        """
        response = requests.post(f"{self.gate_url}/evaluate", json={
            "action_class": action_class,
            "target_type": target_type,
            "content": content,
            "agent_name": self.agent_name,
            **kwargs
        })
        return response.json()


class ExecutionBlocked(Exception):
    pass


# --- Usage in your agent ---

gate = CASAGate(agent_name="my-agent")

def agent_transfer_funds(amount, destination):
    # Governance check BEFORE execution
    result = gate.guard(
        action_class="MANIPULATE",
        target_type="INSTITUTION",
        content=f"Transfer ${amount} to {destination}"
    )
    
    if result["verdict"] == "REFUSE":
        print(f"Blocked: {result['reasoning']}")
        return None
    
    if result["verdict"] == "GOVERN":
        print(f"Proceeding with constraints (trace: {result['trace_hash']})")
        # apply constraints here if needed
    
    # actual transfer logic here
    execute_transfer(amount, destination)
```

---

## 4. Check gate health and stats

```python
import requests

GATE_URL = "https://casa-gate.onrender.com"

# Health check
health = requests.get(f"{GATE_URL}/health").json()
print(health)
# {
#   "status": "live",
#   "gate_version": "CASA-GATE-4.0.0-REGISTRY-GRAPH",
#   "primitives": 93,
#   "hard_stops": 3,
#   "uptime_since": "2026-03-11T21:21:40"
# }

# Aggregate stats
stats = requests.get(f"{GATE_URL}/stats").json()
print(f"Total evaluations: {stats['total_evaluations']}")
print(f"Verdict breakdown: {stats['verdicts']}")
```

---

## 5. Action class reference

| Action Class | Typical Verdict | Use When |
|---|---|---|
| QUERY | ACCEPT | Reading data, retrieving information |
| EXPLAIN | ACCEPT | Generating explanations or reports |
| CREATE | ACCEPT | Creating content or artifacts |
| ANALYZE | ACCEPT | Running analysis or reasoning |
| ASSIST | ACCEPT | General task assistance |
| PERSUADE | GOVERN | Influencing decisions or behavior |
| ADVISE | GOVERN | Giving recommendations |
| NEGOTIATE | GOVERN | Negotiating terms or agreements |
| MANIPULATE | REFUSE | Attempting to control without consent |
| DECEIVE | REFUSE | Misrepresenting information |
| COERCE | REFUSE | Forcing action through threat or pressure |
| HARM | REFUSE | Direct harm to person or system |
| UNDECLARED | GOVERN | Unknown or undeclared intent |

## 6. Target type reference

| Target Type | Examples |
|---|---|
| SELF | User acting on their own account |
| OBJECT | Files, systems, databases |
| INFORMATION | Data retrieval, knowledge queries |
| PERSON_CONSENTING | User who has opted in |
| PERSON_NONCONSENTING | Third party without consent |
| GROUP | Multiple people, teams, client bases |
| INSTITUTION | Companies, banks, platforms, governments |
| MINOR | Anyone under 18 |
| UNDECLARED | Unknown target |

---

## Next steps

- Interactive API explorer: https://casa-gate.onrender.com/docs
- Full architecture: see `ARCHITECTURE.md`
- CAV specification: see `CANONICAL_ACTION_VECTOR.md`  
- Integration patterns (gateway, sidecar, embedded): see `docs/integration.md`
- Enterprise evaluation or NDA package: contact@resonanceinstitutellc.com
