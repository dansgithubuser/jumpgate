#arguments
import argparse
parser=argparse.ArgumentParser(description='calculate a short mining route')
parser.add_argument('type', choices=['ice', 'prec', 'semi', 'rad'])
parser.add_argument('number', type=int, help='number of roids to visit')
parser.add_argument('--roids', default='myrotaroids2.txt')
parser.add_argument('--gates', default='JG_Gate_Cords_(0.7).txt')
parser.add_argument('--ideal-distance', type=int, default=100000)
parser.add_argument('--avoid-space', help='ignore sectors in space that matches supplied regex (case-insensitive)')
parser.add_argument('--all', action='store_true', help='print all routes being considered')
args=parser.parse_args()

#helpers
class Point:
	def __init__(self, list): self.coordinates=[float(i) for i in list]

	def distance(self, other):
		from math import sqrt
		return sqrt(sum([(self.coordinates[i]-other.coordinates[i])**2 for i in range(3)]))

def lower_entropy(s):
	from re import sub
	return sub(r"[\s'`-]+|^the|station$", '', s.lower())

def at(list, i):
	if 0<=i and i<len(list):
		return list[i]
	else:
		return None

def avoid(sector):
	if not args.avoid_space: return False
	import re
	return re.match(args.avoid_space, sectors[sector].space, re.I)

#parse roids file
class Roid:
	def __init__(self, sector, position, notes):
		self.sector=sector
		self.position=position
		self.notes=notes

	def __str__(self):
		return ' '.join([str(i/1000) for i in self.position.coordinates]+[self.notes])

with open(args.roids) as file: lines=file.readlines()[1:]
roids=[]
for line in lines:
	list=line.split(';')
	if len(list)==0: continue
	if not list[6].startswith(args.type): continue
	if list[7]!='big': continue
	roids.append(Roid(
		lower_entropy(list[2]),
		Point(list[3:6]),
		list[9]
	))

#parse gates file
class Sector:
	def __init__(self, name, roids, space):
		self.name=name
		self.roids=roids
		self.space=space

with open(args.gates) as file: lines=file.readlines()[1:]
from collections import defaultdict
gates=defaultdict(dict)
sectors={}
for line in lines:
	list=line.split('\t')
	if len(list)==0: continue
	sector=lower_entropy(list[1])
	gates[sector][lower_entropy(list[2])]=Point(list[3:6])
	sector_roids=[]
	for i in range(len(roids)):
		if roids[i].sector==sector:
			sector_roids.append(i)
	sectors[sector]=Sector(list[1], sector_roids, list[0])

#sector routing
class SectorRouter:
	def __init__(self):
		self.routes={}

	def route(self, sector, start=None, end=None):
		#check for cached value
		a=(sector, start, end)
		if a in self.routes: return self.routes[a]
		#simple iterative solution to traveling salesperson problem
		def total_distance(route):
			result=0.0
			if len(route)==0 and start and end:
				result+=gates[sector][start].distance(gates[sector][end])
			if len(route) and start:
				result+=gates[sector][start].distance(roids[route[0]].position)
			if len(route) and end:
				result+=gates[sector][end].distance(roids[route[-1]].position)
			for i in range(len(route)-1):
				result+=roids[route[i]].position.distance(roids[route[i+1]].position)
			return result
		def flipped(route, i, j):
			result=route[:i]
			for k in range(j, i-1, -1): result=result+[route[k]]
			result=result+route[j+1:]
			return result
		from copy import deepcopy
		route=deepcopy(sectors[sector].roids)
		best_distance=total_distance(route)
		while True:
			did_something=False
			for i in range(len(route)):
				for j in range(i+1, len(route)):
					idea=flipped(route, i, j)
					idea_distance=total_distance(idea)
					if idea_distance<best_distance:
						route=idea
						best_distance=idea_distance
						did_something=True
						break
				if did_something: break
			if not did_something: break
		#cache and return
		self.routes[a]=(len(route), best_distance, route)
		return self.routes[a]

sector_router=SectorRouter()

#create a route out of each sector that has at least 1 roid
class Route:
	def __init__(self, sector):
		self.sectors=[sector]
		self._value()

	def __eq__(self, other): return sorted(self.sectors)==sorted(other.sectors)

	def append(self, sector):
		self.sectors.append(sector)
		self._value()

	def report(self):
		print('-'*72)
		for sector in self.sectors:
			print(sectors[sector].name)
			for roid in self.route[sector]:
				print('\t{0}'.format(roids[roid]))
		print()
		print('roids: {0}'.format(self.roids))
		print('distance: {0}k'.format(int(self.distance/1000)))
		print('-'*72)

	def _value(self):
		self.roids=0
		self.distance=0
		self.route={}
		for i in range(len(self.sectors)):
			x=sector_router.route(
				self.sectors[i],
				start=at(self.sectors, i-1),
				end=at(self.sectors, i+1)
			)
			self.roids+=x[0]
			self.distance+=x[1]
			self.route[self.sectors[i]]=x[2]

routes=[Route(i) for i in sectors if not avoid(i)]
routes=[x for x in routes if x.roids>=1]

#while there is no route which visits enough roids
while True:
	#report progress, check if enough roids visisted
	if args.all:
		for route in routes:
			route.report()
	else:
		routes[0].report()
	if routes[0].roids>=args.number: break
	#append an unvisited unavoided sector to each route
	new_routes=[]
	for route in routes:
		for next_sector in gates[route.sectors[-1]]:
			if next_sector not in route.sectors and not avoid(next_sector):
				from copy import deepcopy
				new_route=deepcopy(route)
				new_route.append(next_sector)
				new_routes.append(new_route)
	routes=new_routes
	#cull
	i=0
	while i<len(routes):
		routes=[routes[j] for j in range(len(routes)) if j<=i or routes[j]!=routes[i]]
		i+=1
	routes=sorted(routes, key=lambda x: -x.roids/(x.distance+args.ideal_distance))[:len(sectors)]
