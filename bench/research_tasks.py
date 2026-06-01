"""Research/knowledge tasks with ground-truth fact-sets (recall is scorable).

Generalizes the benchmark beyond code: each task is a question whose correct
answer is a known set of facts. We score how many the harness recovers (recall)
and flag claims matching no known fact (possible hallucination/extra). Verification
for research = fact-check, so a strong verifier should keep recall while catching
wrong claims — the same accuracy stack as code, different domain.
"""

from bench.tasks import Bug, BugTask  # reuse: a "fact" == Bug(name, signatures)

_SOLID = BugTask(
    id="solid",
    prompt="List the five SOLID principles of object-oriented design and explain what each means.",
    code="",
    planted=[
        Bug("single_responsibility", "fact", [["single", "responsib"], ["one reason to change"]]),
        Bug("open_closed", "fact", [["open", "closed"], ["open for extension"]]),
        Bug("liskov", "fact", [["liskov"], ["substitut"], ["subtype"]]),
        Bug("interface_segregation", "fact", [["interface", "segregat"], ["many", "specific", "interface"]]),
        Bug("dependency_inversion", "fact", [["dependency", "inversion"], ["depend", "abstraction"]]),
    ],
)
_ACID = BugTask(
    id="acid",
    prompt="What are the ACID properties of a database transaction, and what does each guarantee?",
    code="",
    planted=[
        Bug("atomicity", "fact", [["atomic"], ["all or nothing"]]),
        Bug("consistency", "fact", [["consisten"], ["valid state"]]),
        Bug("isolation", "fact", [["isolat"], ["concurrent", "transaction"]]),
        Bug("durability", "fact", [["durab"], ["persist", "crash"]]),
    ],
)
_HTTP = BugTask(
    id="http_status",
    prompt="What are the five categories of HTTP status codes (1xx–5xx) and what does each category mean?",
    code="",
    planted=[
        Bug("1xx", "fact", [["1xx", "informational"], ["100", "continue"], ["informational"]]),
        Bug("2xx", "fact", [["2xx", "success"], ["200", "ok"], ["success"]]),
        Bug("3xx", "fact", [["3xx", "redirect"], ["301", "302"], ["redirect"]]),
        Bug("4xx", "fact", [["4xx", "client error"], ["404"], ["client error"]]),
        Bug("5xx", "fact", [["5xx", "server error"], ["500"], ["server error"]]),
    ],
)
_CAP = BugTask(
    id="cap",
    prompt="State the CAP theorem: what are its three properties and what does it claim about distributed systems?",
    code="",
    planted=[
        Bug("consistency", "fact", [["consisten"]]),
        Bug("availability", "fact", [["availab"]]),
        Bug("partition_tolerance", "fact", [["partition", "toleran"], ["network partition"]]),
        Bug("only_two", "fact", [["two of", "three"], ["can only guarantee two"], ["pick two"], ["cannot have all three"]]),
    ],
)
_PY310 = BugTask(
    id="python310",
    prompt="What are the key new features introduced in Python 3.10?",
    code="",
    planted=[
        Bug("pattern_matching", "fact", [["match", "case"], ["structural pattern matching"], ["pattern matching"]]),
        Bug("paren_context", "fact", [["parenthesized context manager"], ["parenthes", "with"]]),
        Bug("better_errors", "fact", [["better error", "message"], ["precise", "error"], ["improved", "syntaxerror"]]),
        Bug("union_operator", "fact", [["union", "operator"], ["x | y", "type"], ["|", "type hint"]]),
    ],
)

RESEARCH_TASKS = [_SOLID, _ACID, _HTTP, _CAP, _PY310]
