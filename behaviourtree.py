from typing import Callable
import time

def lerp(a: float, b: float, f: float):
    return a * (1.0 - f) + (b * f)

def map(x: float, in_min: float, in_max: float, out_min: float, out_max: float):
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def clamp(num, min_value, max_value):
    num = max(min(num, max_value), min_value)
    return num

class BehaviourNode(object):
	def __init__(self, tree, name: str, duration: float = 1.0):
		self.edges = {}
		self.tree = tree
		self.name = name
		self.strength = 0.0
		self.transition_duration = duration
		self.is_transitioning = False

	def connect_node(self, node, condition: Callable[[], bool]) -> None:
		self.edges[node] = condition

	def tick(self):
		for node, condition in self.edges.items():
			if condition() and not node.is_transitioning:
				self.tree.transition_to_active_node(node, self.transition_duration)
				self.on_transition_start()

	def on_transition_start(self):
		pass

	def on_transition_end(self):
		pass


class BehaviourTree(object):
	def __init__(self):
		self.nodes = []
		self.active_node = None
		self.transitioning_node = None

	def tick(self) :
		if self.transitioning_node:
			elapsed = time.time() - self.transition_start_time

			# Lerp between each node
			self.active_node.strength = clamp(map( self.transition_start_time + elapsed, self.transition_start_time, self.transition_end_time, 1.0, 0.0), 0.0, 1.0)
			self.transitioning_node.strength = clamp(map( self.transition_start_time + elapsed, self.transition_start_time, self.transition_end_time, 0.0, 1.0), 0.0, 1.0)

			# Transition finished
			if self.transition_start_time + elapsed >= self.transition_end_time:
				self.active_node.is_transitioning = False
				self.active_node = self.transitioning_node
				self.active_node.on_transition_end()
				self.transitioning_node = None

		if self.active_node:
			self.active_node.tick()

		if self.transitioning_node:
			self.transitioning_node.tick()


	def add_node(self, node: BehaviourNode) -> None:
		self.nodes.append(node)

	def transition_to_active_node(self, target_node: BehaviourNode, duration: float) -> None:
		self.transitioning_node = target_node
		self.transition_start_time = time.time()
		self.transition_end_time = self.transition_start_time + duration
		self.transitioning_node.is_transitioning = True
		self.active_node.is_transitioning = True

	def set_active_node(self, node: BehaviourNode) -> None:
		self.active_node = node
		self.active_node.strength = 1.0
		self.active_node.is_transitioning = False


if __name__ == "__main__":
	tree = BehaviourTree()

	node_A = BehaviourNode(tree, "Node A")
	node_B = BehaviourNode(tree, "Node B")
	node_C = BehaviourNode(tree, "Node C")

	tree.add_node(node_A)
	tree.add_node(node_B)
	tree.set_active_node(node_A)

	count = 0

	node_A.connect_node(node_B, lambda: True if count > 10 else False)
	node_B.connect_node(node_C, lambda: True if count > 30 else False)

	while node_C.strength < 1.0:
		count += 1
		tree.tick()
		time.sleep(0.1)

		print(f"Count: {count}, Active node: {tree.active_node.name}, Node A strength: {node_A.strength}, Node B strength: {node_B.strength} Node C strength: {node_C.strength}")
