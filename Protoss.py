import random
from random import randrange
from turtle import position
from sc2.bot_ai import BotAI as AI
from sc2.data import Difficulty, Race
from sc2.main import run_game
from sc2.player import Bot, Computer
from sc2.unit import Unit
from sc2 import maps
from sc2.ids.unit_typeid import UnitTypeId

class Nightmare(AI):
    def __init__(self):
        self.raw_affects_selection = True
    
    async def on_start(self):
        self.client.game_step = 4
    
    async def on_step(self, iteration:int):
        if iteration%100 == 0:
            print(f"Interation: {iteration}")
        
        if self.townhalls:
            #self explanitory
            await self.distribute_workers()
            #train probes until optimal amount
            await self.train_probes(max = self.townhalls[0].ideal_harvesters)
            #construct vespene extractors
            await self.construct_gas()
            #construct supply if needed
            await self.construct_supply()
            #construct forge(s)
            await self.construct_forge(max=1) #more advanced logic is needed for 2 forges D:    (stradegy wise)
            #expand until 3 townhalls total
            await self.expand(max = 3)
            #build turret defenses
            await self.construct_photon_cannon()
            
        else:
            await self.expand()
                
    async def expand(self, max=3):
        if self.townhalls.amount < max and self.can_afford(UnitTypeId.NEXUS) and (self.already_pending(UnitTypeId.NEXUS) + self.structures.filter(lambda structure: structure.type_id == UnitTypeId.NEXUS and structure.is_ready).amount) < max and self.workers:
            await self.expand_now()
                
    async def train_probes(self, max=16):
        if (self.townhalls[0].is_idle and self.can_afford(UnitTypeId.PROBE) and self.structures(UnitTypeId.PROBE).amount < max) and self.townhalls:
            self.townhalls[0].train(UnitTypeId.PROBE)
            
    async def getWorker(self, pos):
        #Get all idle workers (closest worker if no idle) and select the one closest to the target position and return it
        return self.workers.filter(lambda worker: (worker.is_collecting or worker.is_idle) and worker.tag not in self.unit_tags_received_action).closest_to(pos) or self.workers.closest_to(pos)
        
    async def construct_gas(self):
        if self.can_afford(UnitTypeId.ASSIMILATOR) and self.workers:
            for hall in self.townhalls:
                if len(self.vespene_geyser.closer_than(25, hall)) > 0:
                    for vespene in self.vespene_geyser.closer_than(25, hall): 
                        if not self.structures(UnitTypeId.ASSIMILATOR).closer_than(1.0, vespene).exists and vespene.has_vespene: 
                            #use closest worker to build the assimilator
                            await self.build(UnitTypeId.ASSIMILATOR, near = vespene, build_worker = await self.getWorker(pos=vespene))
     
    async def construct_supply(self):
        if self.can_afford(UnitTypeId.PYLON) and not self.already_pending(UnitTypeId.PYLON) and self.workers:
            if self.supply_left <= 5:
                #get random enemy start location
                if len(self.enemy_start_locations) == 1:
                    ran = 0
                else:
                    ran = randrange(0, len(self.enemy_start_locations))
                enemy = self.enemy_start_locations[ran]

                #Check if no pylons exist
                if self.structures(UnitTypeId.PYLON).amount < 1:
                    pos = self.townhalls[0].position.towards(self.game_info.map_center, 5)
                #If they do exist then build them 8 away from the closest one to the enemy towards the enemy
                else:
                    if self.structures(UnitTypeId.PHOTONCANNON):
                        base = self.structures(UnitTypeId.PHOTONCANNON).closest_to(enemy)
                    else:
                        base = self.structures(UnitTypeId.PYLON).closest_to(enemy)
                    pos = base.position.towards(enemy, 5)
                    #if a townhall is closer then palce there isntead of a case where you place between minerals and townhall
                    hall = self.townhalls.closest_to(self.game_info.map_center)
                    if hall.distance_to(self.game_info.map_center) < pos.distance_to(self.game_info.map_center):
                        pos = hall.position.towards(enemy, 5)
                            
                await self.build(UnitTypeId.PYLON, near = pos, build_worker = await self.getWorker(pos=pos))
                
            else:
                for structure in self.structures:                         #These structures do not need power
                    if not structure.is_powered and (structure.name not in ["Pylon", "Nexus", "Assimilator"]) and structure.is_ready:
                        pos = structure.position.towards(self.game_info.map_center, 3)
                        await self.build(UnitTypeId.PYLON, near = pos, build_worker = await self.getWorker(pos=pos))
                        
    async def construct_forge(self, max=1):
        #dont have more then 1 forge, and make sure you have at least 2 assimilators
        if self.can_afford(UnitTypeId.FORGE) and not self.already_pending(UnitTypeId.FORGE) and self.structures(UnitTypeId.FORGE).amount < max and self.structures(UnitTypeId.ASSIMILATOR).amount >= 2 and self.workers:
            #get the furthest assimilator from your closest ramp
            assimilator = self.structures(UnitTypeId.ASSIMILATOR).furthest_to(self.main_base_ramp.top_center)
            pos = assimilator.position.towards(-self.main_base_ramp.top_center, 8)
            await self.build(UnitTypeId.FORGE, near = pos, build_worker = await self.getWorker(pos=pos))
    
    async def construct_photon_cannon(self):
        if self.can_afford(UnitTypeId.PHOTONCANNON) and not self.already_pending(UnitTypeId.PHOTONCANNON) and self.structures(UnitTypeId.FORGE) and self.enemy_units and self.workers:
            #get random enemy start location
            if len(self.enemy_start_locations) == 1:
                ran = 0
            else:
                ran = randrange(0, len(self.enemy_start_locations))
            enemy = self.enemy_start_locations[ran]
            
            #Check to see if zerg are near first nexus
            if self.enemy_units.closest_to(self.townhalls[0]).distance_to(self.townhalls[0]) < 20:
                #if they are not then just build basic defense
                if self.structures(UnitTypeId.PHOTONCANNON).amount == 0:
                    pos = self.main_base_ramp.top_center
                elif self.structures(UnitTypeId.PHOTONCANNON).amount == 1:
                    if self.main_base_ramp.top_center < self.main_base_ramp.bottom_center:
                        pos = self.main_base_ramp.top_center-self.main_base_ramp.bottom_center
                    else:
                        pos = self.main_base_ramp.bottom_center-self.main_base_ramp.top_center
                elif self.structures(UnitTypeId.PHOTONCANNON).amount == 2:
                    pos = self.main_base_ramp.bottom_center
                else:
                    pos = self.structures(UnitTypeId.PHOTONCANNON).closest_to(enemy).position.towards(enemy, 3)
                await self.build(UnitTypeId.PHOTONCANNON, near = pos, build_worker = await self.getWorker(pos=pos))
            else:
                #if they are then position is towards the enemy with little spacing
                pos = self.townhalls[0].position.towards(self.enemy_units.closest_to(self.townhalls[0]).position, 1)
            
            await self.build(UnitTypeId.PHOTONCANNON, near = pos, build_worker = await self.getWorker(pos=pos))
        
run_game(
    maps.get("2000AtmospheresAIE"),
    [Bot(Race.Protoss, Nightmare()), Computer(Race.Zerg, Difficulty.Hard)],
    realtime = False
)
