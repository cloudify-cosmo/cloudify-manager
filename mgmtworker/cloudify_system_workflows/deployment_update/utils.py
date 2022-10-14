def clear_graph(graph):
    """Remove all tasks from the graph"""
    for task in graph.tasks:
        graph.remove_task(task)
