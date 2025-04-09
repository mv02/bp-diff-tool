from ..driver import driver
from ..utils.conversions import edge_to_cy, node_to_cy
from .types import CytoscapeEdge, CytoscapeNode, Edge


def fetch_method(
    id: str,
    graph_name: str,
    with_entrypoint: bool = False,
):
    query = """MATCH (m {id: $id, graph: $graph})
    OPTIONAL MATCH (caller)-->(m)
    OPTIONAL MATCH (m)-->(callee)
    OPTIONAL MATCH p = ALL SHORTEST (e {graph: $graph})-->+(m)
    WHERE e.is_entrypoint
    RETURN m, collect(DISTINCT caller) AS callers,
    collect(DISTINCT callee) AS callees, p AS path"""

    records = driver.execute_query(query, id=id, graph=graph_name).records

    cy_nodes: dict[str, list[CytoscapeNode]] = {}
    cy_edges: dict[str, CytoscapeEdge] = {}

    path_nodes: list[list[CytoscapeNode]] = []
    path_edges: list[CytoscapeEdge] = []

    for record in records:
        m, callers, callees, path = record

        if with_entrypoint and path is not None:
            path_nodes = [
                list(node_to_cy(node).values())[0]
                for node in path.nodes
                if node["id"] != id
            ]

            for rel in path.relationships:
                edge: Edge = {
                    "source": rel.start_node["id"],
                    "target": rel.end_node["id"],
                    "value": rel["value"],
                }
                path_edges.append(list(edge_to_cy(edge).values())[0])

        cy_nodes |= node_to_cy(m)

        method_node = cy_nodes[id][0]
        method_node["data"]["callers"] = []
        method_node["data"]["callees"] = []

        for caller in callers:
            definition = list(node_to_cy(caller).values())[0]
            method_node["data"]["callers"].append(definition)
        for callee in callees:
            definition = list(node_to_cy(callee).values())[0]
            method_node["data"]["callees"].append(definition)

    return {
        "nodes": list(cy_nodes.values()),
        "edges": list(cy_edges.values()),
        "path": {"nodes": path_nodes, "edges": path_edges},
    }


def fetch_method_callers(graph_name: str, method_id: str, caller_id: str | None = None):
    if caller_id is None:
        query = """MATCH (m {id: $id, graph: $graph})
        OPTIONAL MATCH (caller)-[r]->(m)
        OPTIONAL MATCH (neighbor_caller)-->(caller)
        OPTIONAL MATCH (caller)-->(neighbor_callee)
        RETURN caller, r, collect(DISTINCT neighbor_caller) AS neighbor_callers,
        collect(DISTINCT neighbor_callee) AS neighbor_callees"""
    else:
        query = """MATCH (m {id: $id, graph: $graph})
        OPTIONAL MATCH (caller {id: $caller_id})-[r]->(m)
        OPTIONAL MATCH (neighbor_caller)-->(caller)
        OPTIONAL MATCH (caller)-->(neighbor_callee)
        RETURN caller, r, collect(DISTINCT neighbor_caller) AS neighbor_callers,
        collect(DISTINCT neighbor_callee) AS neighbor_callees"""

    records = driver.execute_query(
        query, id=method_id, caller_id=caller_id, graph=graph_name
    ).records

    cy_nodes: dict[str, list[CytoscapeNode]] = {}
    cy_edges: dict[str, CytoscapeEdge] = {}

    for record in records:
        caller, r, neighbor_callers, neighbor_callees = record
        if caller is None:
            continue
        edge: Edge = {
            "source": caller["id"],
            "target": method_id,
            "value": r["value"],
        }
        cy_nodes |= node_to_cy(caller)
        cy_edges |= edge_to_cy(edge)

        caller_node = cy_nodes[caller["id"]][0]
        caller_node["data"]["callers"] = []
        caller_node["data"]["callees"] = []

        for caller in neighbor_callers:
            definition = list(node_to_cy(caller).values())[0]
            caller_node["data"]["callers"].append(definition)
        for callee in neighbor_callees:
            definition = list(node_to_cy(callee).values())[0]
            caller_node["data"]["callees"].append(definition)

    return {"nodes": list(cy_nodes.values()), "edges": list(cy_edges.values())}


def fetch_method_callees(graph_name: str, method_id: str, callee_id: str | None = None):
    if callee_id is None:
        query = """MATCH (m {id: $id, graph: $graph})
        OPTIONAL MATCH (m)-[r]->(callee)
        OPTIONAL MATCH (neighbor_caller)-->(callee)
        OPTIONAL MATCH (callee)-->(neighbor_callee)
        RETURN callee, r, collect(DISTINCT neighbor_caller) AS neighbor_callers,
        collect(DISTINCT neighbor_callee) AS neighbor_callees"""
    else:
        query = """MATCH (m {id: $id, graph: $graph})
        OPTIONAL MATCH (m)-[r]->(callee {id: $callee_id})
        OPTIONAL MATCH (neighbor_caller)-->(callee)
        OPTIONAL MATCH (callee)-->(neighbor_callee)
        RETURN callee, r, collect(DISTINCT neighbor_caller) AS neighbor_callers,
        collect(DISTINCT neighbor_callee) AS neighbor_callees"""

    records = driver.execute_query(
        query, id=method_id, callee_id=callee_id, graph=graph_name
    ).records

    cy_nodes: dict[str, list[CytoscapeNode]] = {}
    cy_edges: dict[str, CytoscapeEdge] = {}

    for record in records:
        callee, r, neighbor_callers, neighbor_callees = record
        if callee is None:
            continue
        edge: Edge = {
            "source": method_id,
            "target": callee["id"],
            "value": r["value"],
        }
        cy_nodes |= node_to_cy(callee)
        cy_edges |= edge_to_cy(edge)

        callee_node = cy_nodes[callee["id"]][0]
        callee_node["data"]["callers"] = []
        callee_node["data"]["callees"] = []

        for caller in neighbor_callers:
            definition = list(node_to_cy(caller).values())[0]
            callee_node["data"]["callers"].append(definition)
        for callee in neighbor_callees:
            definition = list(node_to_cy(callee).values())[0]
            callee_node["data"]["callees"].append(definition)

    return {"nodes": list(cy_nodes.values()), "edges": list(cy_edges.values())}
