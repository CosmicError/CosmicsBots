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
from sc2.ids.ability_id import AbilityId
from sc2.ids.upgrade_id import UpgradeId

class Nightmare(AI):
    def __init__(self):
        self.raw_affects_selection = True
    
    async def on_start(self):
        self.client.game_step = 4
    
    async def on_step(self, iteration:int):
        if iteration%100 == 0:
            print(f"tick: {iteration}")
        
        #distribute workers
        await self.distribute_workers()
        
        #Attacking
        if self.units(UnitTypeId.VOIDRAY):
            #attack using void rays if at least 5
            await self.attack_voidray(min=10)
        
        #Building/Training
        if self.townhalls:
            #train void rays
            await self.train_voidray(max=20)
            #train probes until optimal amount
            await self.train_probes(max = self.townhalls.first.ideal_harvesters)
            #construct vespene extractors
            await self.construct_gas()
            #construct supply if needed
            await self.construct_supply()
            #construct forge(s)
            await self.construct_forge(max=1) #more advanced logic is needed for 2 forges D:    (stradegy wise)
            #build turret defenses
            await self.construct_photon_cannon()
            #construct a gate so we can build more stuffs
            await self.construct_warpgate(max=1)
            #make a cybernetics core
            await self.construct_cybernetics_core(max=1)
            #make star gates so we can construct void rays
            await self.construct_stargate(max=6)
            #expand until 3 townhalls total
            await self.expand(max = 3)
            #removes idle harvesters leaving only 10 idle
            #await self.delete_idle(min=10)
            
        else:
            await self.expand()
        
        #RESEARCH
        if self.structures(UnitTypeId.CYBERNETICSCORE):
            await self.research_voidray()
            
            await self.research_warpgate()
            
            await self.research_air_weapons()
            
            await self.research_air_defense()
            
                
    async def expand(self, max=3):
        if self.townhalls.amount < max and self.can_afford(UnitTypeId.NEXUS) and (self.already_pending(UnitTypeId.NEXUS) + self.structures.filter(lambda structure: structure.type_id == UnitTypeId.NEXUS and structure.is_ready).amount) < max and self.workers:
            await self.expand_now()
    
    #---------------------------------------
    
    async def train_probes(self, max=16):
        if (self.townhalls.first.is_idle and self.can_afford(UnitTypeId.PROBE) and self.structures(UnitTypeId.PROBE).amount < max) and self.townhalls:
            self.townhalls.first.train(UnitTypeId.PROBE)
            
    async def train_voidray(self, max=10):
        if self.can_afford(UnitTypeId.VOIDRAY) and self.units(UnitTypeId.VOIDRAY).amount < max and self.structures(UnitTypeId.STARGATE):
            for gate in self.structures(UnitTypeId.STARGATE).ready.idle:
                if self.can_afford(UnitTypeId.VOIDRAY) and self.units(UnitTypeId.VOIDRAY).amount < max:
                    gate.train(UnitTypeId.VOIDRAY)
    
    async def delete_idle(self, min=10):
        if self.workers:
            idle = []
            for worker in self.workers:
                if worker and worker.is_idle:
                    idle.append(worker)
            
            if len(idle) > min:
                for worker in idle[0, len(idle)-min]:
                    if worker:
                        self.units(UnitTypeId.PROBE).remove()
    #---------------------------------------
    
    def getWorker(self, pos):
        workers_ = self.workers
        #Get all idle workers (closest worker if no idle) and select the one closest to the target position and return it
        avalibe = workers_.filter(lambda worker: (worker.is_collecting or worker.is_idle) and worker.tag not in self.unit_tags_received_action)
        if avalibe:
            return avalibe.closest_to(pos)
        else:
            return workers_.closest_to(pos)
        
    async def construct_gas(self):
        if self.can_afford(UnitTypeId.ASSIMILATOR) and self.workers:
            for hall in self.townhalls:
                if len(self.vespene_geyser.closer_than(25, hall)) > 0:
                    for vespene in self.vespene_geyser.closer_than(25, hall): 
                        if not self.structures(UnitTypeId.ASSIMILATOR).closer_than(1.0, vespene).exists and vespene.has_vespene: 
                            #use closest worker to build the assimilator
                            await self.build(UnitTypeId.ASSIMILATOR, near = vespene, build_worker = self.getWorker(pos=vespene))
     
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
                    pos = self.townhalls.first.position.towards(self.game_info.map_center, 5)
                #If they do exist then build them 5 away from the closest one to the enemy towards the enemy
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
                            
                await self.build(UnitTypeId.PYLON, near = pos, build_worker = self.getWorker(pos=pos))
                
            else:
                for structure in self.structures:                         #These structures do not need power
                    if not structure.is_powered and (structure.name not in ["Pylon", "Nexus", "Assimilator"]) and structure.is_ready and structure:
                        pos = structure.position.towards(self.game_info.map_center, 3)
                        await self.build(UnitTypeId.PYLON, near = pos, build_worker = self.getWorker(pos=pos))
                        
    async def construct_forge(self, max=1):
        #dont have more then 1 forge, and make sure you have at least 2 assimilators
        if self.can_afford(UnitTypeId.FORGE) and not self.already_pending(UnitTypeId.FORGE) and self.structures(UnitTypeId.FORGE).amount < max and self.structures(UnitTypeId.ASSIMILATOR).amount >= 2 and self.workers:
            #get the furthest assimilator from your closest ramp
            assimilator = self.structures(UnitTypeId.ASSIMILATOR).furthest_to(self.main_base_ramp.top_center)
            pos = assimilator.position.towards(-self.main_base_ramp.top_center, 8)
            await self.build(UnitTypeId.FORGE, near = pos, build_worker = self.getWorker(pos=pos))
    
    async def construct_photon_cannon(self):
        if (self.can_afford(UnitTypeId.PHOTONCANNON) 
            and (self.already_pending(UnitTypeId.PHOTONCANNON) + self.structures.filter(lambda structure: structure.type_id == UnitTypeId.PHOTONCANNON and structure.is_ready).amount) < 3 
            and self.structures(UnitTypeId.FORGE) 
            and self.enemy_units 
            and self.workers):
            
            #get random enemy start location
            if len(self.enemy_start_locations) == 1:
                ran = 0
            else:
                ran = randrange(0, len(self.enemy_start_locations))
            enemy = self.enemy_start_locations[ran]
            
            await self.build(UnitTypeId.PHOTONCANNON, near = self.townhalls.first, build_worker = self.getWorker(pos=self.townhalls.first))
        
    async def construct_warpgate(self, max=1):
        if self.can_afford(UnitTypeId.GATEWAY) and (self.already_pending(UnitTypeId.GATEWAY) + self.structures.filter(lambda structure: structure.type_id == UnitTypeId.GATEWAY and structure.is_ready).amount) < max:
            pos = self.structures(UnitTypeId.PYLON).closest_to(self.townhalls.first)
            await self.build(UnitTypeId.GATEWAY, near = pos, build_worker = self.getWorker(pos=pos))
    
    async def construct_cybernetics_core(self, max=1):
        if self.can_afford(UnitTypeId.CYBERNETICSCORE) and (self.already_pending(UnitTypeId.CYBERNETICSCORE) + self.structures.filter(lambda structure: structure.type_id == UnitTypeId.CYBERNETICSCORE and structure.is_ready).amount) < max:
            pos = self.structures(UnitTypeId.PYLON).closest_to(self.townhalls.first)
            await self.build(UnitTypeId.CYBERNETICSCORE, near = pos, build_worker = self.getWorker(pos=pos))
    
    async def construct_stargate(self, max=1):
        if self.can_afford(UnitTypeId.STARGATE) and (self.already_pending(UnitTypeId.STARGATE) + self.structures.filter(lambda structure: structure.type_id == UnitTypeId.STARGATE and structure.is_ready).amount) < max:
            pos = self.structures(UnitTypeId.PYLON).closest_to(self.townhalls.first)
            await self.build(UnitTypeId.STARGATE, near = pos, build_worker = self.getWorker(pos=pos))
    
    async def construct_fleetbeacon(self, max=1):
        if self.can_afford(UnitTypeId.FLEETBEACON) and (self.already_pending(UnitTypeId.FLEETBEACON) + self.structures.filter(lambda structure: structure.type_id == UnitTypeId.FLEETBEACON and structure.is_ready).amount) < max:
            pos = self.structures(UnitTypeId.PYLON).closest_to(self.townhalls.first)
            await self.build(UnitTypeId.FLEETBEACON, near = pos, build_worker = self.getWorker(pos=pos))
    
    #---------------------------------------
    
    async def attack_voidray(self, min=5):
        if self.units(UnitTypeId.VOIDRAY).amount >= min:
            if self.all_enemy_units:
                for ray in self.units(UnitTypeId.VOIDRAY).idle:
                    if ray and self.all_enemy_units:
                        ray.attack(self.all_enemy_units.closest_to(self.townhalls.first))
                    
            elif self.enemy_structures:
                for ray in self.units(UnitTypeId.VOIDRAY).idle:
                    if ray and self.enemy_structures:
                        ray.attack(self.enemy_structures.closest_to(self.townhalls.first))
                        
            else:
                #else just attack their starting location
                for ray in self.units(UnitTypeId.VOIDRAY).idle:
                    if ray:
                        ray.attack(self.enemy_start_locations[0])
    
    #---------------------------------------
    
    async def research_voidray(self):
        if self.structures(UnitTypeId.CYBERNETICSCORE).ready and self.can_afford(UpgradeId.VOIDRAYSPEEDUPGRADE):
            self.structures(UnitTypeId.CYBERNETICSCORE).first.research(UpgradeId.VOIDRAYSPEEDUPGRADE, True)
        
    async def research_warpgate(self):
        if self.structures(UnitTypeId.CYBERNETICSCORE).ready and self.can_afford(UpgradeId.WARPGATERESEARCH):
            self.structures(UnitTypeId.CYBERNETICSCORE).first.research(UpgradeId.WARPGATERESEARCH, True)
    
    async def research_air_weapons(self):
        if self.structures(UnitTypeId.CYBERNETICSCORE).ready:
            if self.already_pending_upgrade(UpgradeId.PROTOSSAIRWEAPONSLEVEL1) == 0:
                self.structures(UnitTypeId.CYBERNETICSCORE).first.research(UpgradeId.PROTOSSAIRWEAPONSLEVEL1, True)
            elif self.already_pending_upgrade(UpgradeId.PROTOSSAIRWEAPONSLEVEL2) == 0:
                self.structures(UnitTypeId.CYBERNETICSCORE).first.research(UpgradeId.PROTOSSAIRWEAPONSLEVEL2, True)
            elif self.already_pending_upgrade(UpgradeId.PROTOSSAIRWEAPONSLEVEL3) == 0:
                self.structures(UnitTypeId.CYBERNETICSCORE).first.research(UpgradeId.PROTOSSAIRWEAPONSLEVEL3, True)
                
    async def research_air_defense(self):
        if self.structures(UnitTypeId.CYBERNETICSCORE).ready:
            if self.already_pending_upgrade(UpgradeId.PROTOSSAIRARMORSLEVEL1) == 0:
                self.structures(UnitTypeId.CYBERNETICSCORE).first.research(UpgradeId.PROTOSSAIRARMORSLEVEL1, True)
            elif self.already_pending_upgrade(UpgradeId.PROTOSSAIRARMORSLEVEL2) == 0:
                self.structures(UnitTypeId.CYBERNETICSCORE).first.research(UpgradeId.PROTOSSAIRARMORSLEVEL2, True)
            elif self.already_pending_upgrade(UpgradeId.PROTOSSAIRARMORSLEVEL3) == 0:
                self.structures(UnitTypeId.CYBERNETICSCORE).first.research(UpgradeId.PROTOSSAIRARMORSLEVEL3, True)
    
run_game(
    maps.get("2000AtmospheresAIE"),
    [Bot(Race.Protoss, Nightmare()), Computer(Race.Zerg, Difficulty.VeryHard)], #[VeryEasy] [Easy] [Medium] [MediumHard] [Hard] [Harder] [VeryHard]     WILL BREAK BOT --> [CheatVision] [CheatMoney] [CheatInsane]
    realtime = False
)

