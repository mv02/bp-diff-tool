import csv
import io
import logging
import os
import shutil
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..driver import driver
from ..utils import CytoscapeElement, invoke_to_cy, method_to_cy, methods_to_tree

CSV_DIR = "csv"

logger = logging.getLogger("uvicorn")
logger.propagate = False

router = APIRouter()


@router.get("/graphs")
def get_graphs():
    records = driver.execute_query(
        "MATCH (m:Method) "
        "OPTIONAL MATCH (m)-[r:CALLS]->() "
        "RETURN m.Graph AS name, count(DISTINCT m) AS nodeCount, count(r) AS edgeCount "
        "ORDER BY name"
    ).records
    return [record.data() for record in records]


@router.get("/graphs/{graph_name}/tree")
def get_method_tree(graph_name: str):
    records = driver.execute_query(
        "MATCH (m:Method {Graph: $graph}) RETURN m.Id AS id, m.Name AS name, m.Type AS type ORDER BY type, name",
        graph=graph_name,
    ).records

    methods: list[dict] = []
    for record in records:
        data = record.data()
        methods.append(
            {"id": int(data["id"]), "name": data["name"], "type": data["type"]}
        )
    return methods_to_tree(methods)


@router.get("/graphs/{graph_name}/method/{id}")
def get_method_by_id(graph_name: str, id: str):
    record = driver.execute_query(
        "MATCH (m:Method {Id: $id, Graph: $graph}) "
        "OPTIONAL MATCH p = ALL SHORTEST (e:Method {IsEntryPoint: 'true', Graph: $graph}) "
        "-[:CALLS {Graph: $graph}]->+(m) "
        "RETURN m, nodes(p) AS path LIMIT 1",
        id=id,
        graph=graph_name,
    ).records[0]

    m, path = record
    if path is None:
        return [*method_to_cy(m)]

    result: list[CytoscapeElement] = []
    for m1, m2 in zip(path, path[1:]):
        result += [*method_to_cy(m1), *method_to_cy(m2), invoke_to_cy(m1, m2)]
    return result


@router.get("/graphs/{graph_name}/method/{id}/callers")
def get_method_callers(graph_name: str, id: str):
    record = driver.execute_query(
        "MATCH (m:Method {Graph: $graph, Id: $id}) "
        "OPTIONAL MATCH (caller:Method {Graph: $graph})-->(m) "
        "RETURN m, collect(caller) AS callers",
        id=id,
        graph=graph_name,
    ).records[0]

    m, callers = record
    result: list[CytoscapeElement] = []
    for caller in callers:
        result += [*method_to_cy(caller), invoke_to_cy(caller, m)]
    return result


@router.get("/graphs/{graph_name}/method/{id}/callees")
def get_method_callees(graph_name: str, id: str):
    record = driver.execute_query(
        "MATCH (m:Method {Graph: $graph, Id: $id}) "
        "OPTIONAL MATCH (m)-->(callee:Method {Graph: $graph}) "
        "RETURN m, collect(callee) AS callees",
        id=id,
        graph=graph_name,
    ).records[0]

    m, callees = record
    result: list[CytoscapeElement] = []
    for callee in callees:
        result += [*method_to_cy(callee), invoke_to_cy(m, callee)]
    return result


@router.post("/import")
def import_csv(
    files: Annotated[list[UploadFile], File()],
    timestamps: Annotated[list[int], Form()],
    graph: Annotated[str, Form()],
):
    keys = ["methods", "invokes", "targets"]

    # Most recent files
    newest: dict[str, tuple[UploadFile, int]] = {}

    for f, t in zip(files, timestamps):
        for key in keys:
            if key not in str(f.filename) or ".csv" not in str(f.filename):
                continue
            if key not in newest or t > newest[key][1]:
                newest[key] = (f, t)

    if any(key not in newest for key in keys):
        raise HTTPException(400, f"Could not find a {key} file")

    logger.info(f"Found files: {[f[0].filename for f in newest.values()]}")

    # Save CSV files to filesystem
    location = os.path.join(CSV_DIR, graph)
    os.makedirs(location, exist_ok=True)
    for key in keys:
        with open(os.path.join(location, f"call_tree_{key}.csv"), "wb") as buffer:
            file = newest[key][0].file
            shutil.copyfileobj(file, buffer)
            file.seek(0)
    logger.info(f"CSV files saved to: {os.path.abspath(location)}")

    # Delete all nodes and edges, create uniqueness constraints and indexes
    logger.info("Purging database")
    driver.execute_query("MATCH ()-[r {Graph: $graph}]-() DELETE r", graph=graph)
    driver.execute_query("MATCH (n {Graph: $graph}) DELETE n", graph=graph)
    driver.execute_query(
        "CREATE CONSTRAINT unique_method_id IF NOT EXISTS "
        "FOR (m:Method) REQUIRE (m.Id, m.Graph) IS UNIQUE"
    )
    driver.execute_query(
        "CREATE CONSTRAINT unique_invoke_id IF NOT EXISTS "
        "FOR (i:Invoke) REQUIRE (i.Id, i.Graph) IS UNIQUE"
    )
    driver.execute_query("CREATE INDEX method_id IF NOT EXISTS FOR (m:Method) ON m.Id")
    driver.execute_query("CREATE INDEX invoke_id IF NOT EXISTS FOR (i:Invoke) ON i.Id")
    driver.execute_query(
        "CREATE INDEX method_graph IF NOT EXISTS FOR (m:Method) ON m.Graph"
    )
    driver.execute_query(
        "CREATE INDEX invoke_graph IF NOT EXISTS FOR (i:Invoke) ON i.Graph"
    )

    # Create method nodes
    logger.info("Creating method nodes")
    methods_csv = io.TextIOWrapper(newest["methods"][0].file)
    reader = csv.DictReader(methods_csv)
    (node_count,) = driver.execute_query(
        "UNWIND $data as row CREATE (m:Method {Graph: $graph}) SET m += row RETURN count(*) AS node_count",
        data=[row for row in reader],
        graph=graph,
    ).records[0]

    # Create temporary invoke nodes
    logger.info("Creating temporary invoke nodes")
    invokes_csv = io.TextIOWrapper(newest["invokes"][0].file)
    reader = csv.DictReader(invokes_csv)
    driver.execute_query(
        "UNWIND $data as row CREATE (i:Invoke {Graph: $graph}) SET i += row",
        data=[row for row in reader],
        graph=graph,
    )

    # Create edges between method nodes
    logger.info("Creating edges between method nodes")
    targets_csv = io.TextIOWrapper(newest["targets"][0].file)
    reader = csv.DictReader(targets_csv)
    targets = list(reader)

    for i in range(0, len(targets), 1000):
        batch = targets[i : i + 1000]
        driver.execute_query(
            "UNWIND $data AS row "
            "MATCH (t:Method {Graph: $graph, Id: row.TargetId}) "
            "MATCH (i:Invoke {Graph: $graph, Id: row.InvokeId}) "
            "MATCH (s:Method {Graph: $graph, Id: i.MethodId}) "
            "MERGE (s)-[r:CALLS {Graph: $graph}]->(t) "
            "RETURN count(DISTINCT r) AS edge_count",
            data=batch,
            graph=graph,
        ).records[0]

    (edge_count,) = driver.execute_query(
        "MATCH ()-[r:CALLS {Graph: $graph}]->() RETURN count(r) AS edge_count",
        graph=graph,
    ).records[0]

    # Delete temporary invoke nodes
    logger.info("Deleting temporary invoke nodes")
    driver.execute_query("MATCH (i:Invoke) DELETE i")

    message = f"Imported {node_count} nodes and {edge_count} edges"
    logger.info(message)
    return {"message": message}
