import lea
import operator


class KtRoll(object):

    def __init__(self, target, crit_value=6):
        self.crit_value = crit_value
        self.target = target
        self.base_roll = lea.interval(1,6)

    def check_success(self, roll_values):
        return tuple(['Crit' if roll_value >= self.crit_value else 'Success' if roll_value >= self.target else 'Miss' for roll_value in list(roll_values)])

    def roll(self, amount, rerolls=0, normal_retains=0, crit_retains=0, miss_retains=0):
        roll = self.base_roll.draw(amount, replacement=True).map(self.modify_rolls).map(self.check_success)
        normal_retains = min(amount, normal_retains)
        crit_retains = min(amount, crit_retains)
        miss_retains = min(amount, miss_retains)
        retains = min(normal_retains + crit_retains + miss_retains, amount)
        if retains > 0:
            roll = roll.given(roll[0:retains] == tuple(
                    ['Crit'] * crit_retains +
                    ['Success'] * normal_retains +
                    ['Miss'] * miss_retains
                )
            )
        return lea.joint(
            roll,
            self.base_roll.draw(rerolls, replacement=True).map(self.check_success)
        ).map(self.map_rerolls)

    # placeholder method for factions that can modify their rolls
    def modify_rolls(self, value):
        return value

    def map_rerolls(self, value):
        hits = list(value[0])
        misses = [x for x in hits if x == 'Miss']
        rerolls = list(value[1])
        for miss in misses:
            if len(rerolls) == 0:
                break
            reroll = rerolls.pop()
            if reroll == 'Crit':
                hits.remove('Miss')
                hits.insert(0, 'Crit')
                continue
            if reroll == 'Success':
                hits.remove('Miss')
                hits = [x for x in hits if x == 'Crit'] + ['Success'] + [x for x in hits if x != 'Crit']
                continue
        return tuple(hits)


class KasrkinRoll(KtRoll):

    def __init__(self, target, crit_value=6, elite_points=0):
        self.elite_points = elite_points
        super().__init__(target, crit_value=6)

    def modify_rolls(self, roll_values):
        elite_points = self.elite_points
        final_rolls = []
        misses = [x for x in list(roll_values) if x < self.target]
        misses.sort()
        misses.reverse()
        hits = [x for x in list(roll_values) if x >= self.target]
        hits.sort()
        hits.reverse()
        for roll in misses + hits:
            if roll + elite_points >= self.crit_value:
                elite_points = 0
                final_rolls.append(self.crit_value)
            elif roll < self.target and roll + elite_points >= self.target:
                elite_points = 0
                final_rolls.append(self.target)
            else:
                final_rolls.append(roll)
        return tuple(final_rolls)


class KasrkinRoll1p(KasrkinRoll):

    def __init__(self, target, crit_value=6):
        super().__init__(target, crit_value=6, elite_points=1)


class KasrkinRoll2p(KasrkinRoll):

    def __init__(self, target, crit_value=6):
        super().__init__(target, crit_value=6, elite_points=2)

class KasrkinRoll3p(KasrkinRoll):

    def __init__(self, target, crit_value=6):
        super().__init__(target, crit_value=6, elite_points=3)


# kt_roll(3,4)
# ktd6 = lea.interval(1,6).map(
#     lambda x: 'Crit' if x >= 6 else 'Success' if x>= 3 else 'Miss'
# )
# crits_retains = 0
# a = ktd6.draw(3, replacement=True)
# crits = ['Crit']*crits_retains
# a.given(a[0:crits_retains] == tuple(crits))
# KtRoll(3, 6).roll(4, miss_retains=1)

class Target(object):

    ignore_wounds_on = 0

    def __init__(self, df, sv, ignore_wounds_on=0, wounds=0, name=''):
        self.df = df
        self.sv = sv
        self.name = name
        self.ignore_wounds_on = ignore_wounds_on
        self.wounds = wounds

    def save(self):
        return KtRoll(self.sv)

    def get_defense(self):
        return self.df

    def __str__(self):
        return '{} Sv: {} Df: {}{}'.format(self.name, self.sv, self.df, '' if self.ignore_wounds_on == 0 else ' ignore wounds on {}+'.format(self.ignore_wounds_on))


class Weapon(object):

    ap = 0
    mw = 0
    no_cover = False
    rending = False
    p = 0

    def __init__(self, name, attacks, bs, nd, cd, special_rules=None, crit_rules=None, dice_class=KtRoll):
        self.name = name
        self.attacks = attacks
        self.bs = bs
        self.nd = nd
        self.cd = cd
        self.critical_on = 6
        self.special_rules = special_rules or []
        if 'AP2' in self.special_rules:
            self.ap = 2
        if 'AP1' in self.special_rules:
            self.ap = 1
        if 'MW3' in self.special_rules:
            self.mw = 3
        if 'MW2' in self.special_rules:
            self.mw = 2
        if 'MW1' in self.special_rules:
            self.mw = 1
        if 'No Cover' in self.special_rules:
            self.no_cover = True
        if 'Rending' in self.special_rules:
            self.rending = True
        if 'P1' in self.special_rules:
            self.p = 1
        if 'Lethal 5+' in self.special_rules:
            self.critical_on = 5
        self.crit_rules = crit_rules or []
        self.dice_class = dice_class

    def plot_shoot(self, *kargs, **kwargs):
        desc = ''
        if 'attack_rerolls' in kwargs:
            desc += ' attacker rerolls: {}'.format(kwargs['attack_rerolls'])
        if 'save_rerolls' in kwargs:
            desc += ' save rerolls: {}'.format(kwargs['save_rerolls'])
        title = '{} vs {} {}'.format(self.name, kargs[0], desc)
        self.shoot(*kargs, **kwargs).plot(title=title)

    def shoot(self, target, cover=0, attack_rerolls=0, save_rerolls=0):
        damage_probs = lea.joint(
            self.dice_class(self.bs, self.critical_on).roll(self.attacks, attack_rerolls),
            target.save().roll(target.get_defense() - self.ap, save_rerolls, normal_retains=cover if not self.no_cover else 0)
        ).map(self.resolve_saves).map(self.damage)
        if target.ignore_wounds_on > 0:
            for ignore_it in range(len(damage_probs.pmf_tuple)):
                damage_probs = lea.joint(
                    damage_probs,
                    lea.event((6+1-target.ignore_wounds_on)/6)
                ).map(self.generate_ignores)
            damage_probs = damage_probs.map(self.apply_ignores)
        if target.wounds > 0:
            damage_probs = damage_probs.map(lambda x: self.apply_wounds_limit(target.wounds, x))
        return damage_probs

    def apply_wounds_limit(self, wounds, value):
        return min(wounds, value)

    def apply_ignores(self, value):
        damage, ignores = value
        return damage - ignores[0]

    def generate_ignores(self, value):
        damage_probs, save = value
        saves = 1 if save else 0
        fails = 1 if not save else 0
        if type(damage_probs) is int:
            if damage_probs == 0:
                return (damage_probs, (0, 0))
            return (damage_probs, (saves, fails))
        else:
            damage, ignores = damage_probs
            if damage > ignores[0] + ignores[1]:
                return (damage, (ignores[0] + saves, ignores[1] + fails))
            else:
                return (damage, (ignores[0], ignores[1]))

    def resolve_saves(self, value):
        result = []
        hits, saves = value
        if self.p > 0:
            saves = saves[0:0-self.p]
        normal_hits = operator.countOf(hits, 'Success')
        crit_hits = operator.countOf(hits, 'Crit')
        if self.rending and crit_hits > 0 and normal_hits > 0:
            crit_hits += 1
            normal_hits -= 1
        normal_saves = operator.countOf(saves, 'Success')
        crit_saves = operator.countOf(saves, 'Crit')
        crit_hits = max(0, crit_hits - crit_saves)
        hits = max(0, normal_hits - normal_saves - max(0, crit_saves - crit_hits))
        result += ['Crit']*crit_hits + ['Success']*hits
        return (tuple(result), crit_hits)


    def damage(self, results):
        hits, og_crits = results
        return self.cd*list(hits).count('Crit') + self.nd*list(hits).count('Success') + og_crits*self.mw


class MeleeWeapon(object):
    def __init__(self, name, attacks, ws, nd, cd, special_rules=None, crit_rules=None, dice_class=KtRoll):
        self.name = name
        self.attacks = attacks
        self.ws = ws
        self.nd = nd
        self.cd = cd
        self.mw = 0
        self.critical_on = 6
        self.special_rules = special_rules or []
        if 'Rending' in self.special_rules:
            self.rending = True
        if 'Lethal 5+' in self.special_rules:
            self.critical_on = 5
        self.crit_rules = crit_rules or []
        self.dice_class = dice_class
    
    def get_fight_roll(self, attack_rerolls=0):
        return self.dice_class(
            self.ws, self.critical_on
        ).roll(
            self.attacks,
            min( # cap to min to reduce computation
                self.attacks,
                attack_rerolls + (
                    1 if 'Balanced' in self.special_rules else 0
                ) + (
                    self.attacks if 'Relentless' in self.special_rules else 0
                )
            )
        ).map(self.sort_roll)
    
    def sort_roll(self, roll_values):
        rolls = list(roll_values)
        return tuple(['Crit' for x in rolls if x == 'Crit'] + ['Success' for x in rolls if x == 'Success'] + ['Miss' for x in rolls if x == 'Miss'])

    def damage(self, hits):
        return self.cd*list(hits).count('Crit') + self.nd*list(hits).count('Success') + hits.count('Crit')*self.mw

class Fight(object):
    
    def __init__(self, attacker, weapon1, defender, weapon2):
        self.attacker = attacker
        self.weapon1 = weapon1
        self.defender = defender
        self.weapon2 = weapon2
        
    def fight(self, attacker_rerolls=0, defender_rerolls=0):
        return lea.joint(
            self.weapon1.get_fight_roll(attacker_rerolls),
            self.weapon2.get_fight_roll(defender_rerolls)
        ).map(self.resolve_combat)

    def try_kill(self, current, opponent):
        if opponent['wounds'] - current['weapon'].cd <= 0 and 'Crit' in current['hits']:
            opponent['wounds'] = max(0, opponent['wounds'] - current['weapon'].cd)
            current['hits'].remove('Crit')
            return True
        if opponent['wounds'] - current['weapon'].nd <= 0 and 'Success' in current['hits']:
            opponent['wounds'] = max(0, opponent['wounds'] - current['weapon'].nd)
            current['hits'].remove('Success')
            return True
        return False


    def try_parry(self, current, opponent):
        decision = None
        if opponent['weapon'].damage(opponent['hits']) >= current['wounds'] and opponent['weapon'].damage(opponent['hits'][1:]) < current['wounds']:
            if 'Crit' in opponent['hits'] and 'Crit' in current['hits']:
                decision = 'use-crit-to-parry'
            else:
                if 'Success' in current['hits']:
                    decision = 'use-success-to-parry'
        if not decision and current['weapon'].damage(current['hits'][1:]) >= opponent['wounds']:
            my_hits_copy = [x for x in current['hits']]
        
        if decision == 'use-crit-to-parry':
            current['hits'].remove('Crit')
            if 'Crit' in opponent['hits']:
                opponent['hits'].remove('Crit')
            else:
                opponent['hits'].remove('Success')
            return True
        if decision == 'use-success-to-parry':
            if 'Success' in opponent['hits']:
                current['hits'].remove('Success')
                opponent['hits'].remove('Success')
                return True
        return False
    
    def resolve_combat(self, combat_rolls):
        rolls1, rolls2 = combat_rolls
        finished = False
        current_fighter = {
            'name': self.attacker.name,
            'wounds': self.attacker.wounds,
            'weapon': self.weapon1,
            'hits': [x for x in list(rolls1) if x in ['Crit', 'Success']]
        }
        attacker = current_fighter
        opponent = {
            'name': self.defender.name,
            'wounds': self.defender.wounds,
            'weapon': self.weapon2,
            'hits': [x for x in list(rolls2) if x in ['Crit', 'Success']]
        }
        defender = opponent
        finished = False
        while not finished:
            # No-parry strategy
            done_something = False
            if self.try_kill(current_fighter, opponent):
                done_something = True
            elif self.try_parry(current_fighter, opponent):
                done_something = True
            else:
                if 'Crit' in current_fighter['hits']:
                    opponent['wounds'] = max(0, opponent['wounds'] - current_fighter['weapon'].cd)
                    current_fighter['hits'].remove('Crit')
                elif 'Success' in current_fighter['hits']:
                    opponent['wounds'] = max(0, opponent['wounds'] - current_fighter['weapon'].nd)
                    current_fighter['hits'].remove('Success')
            if opponent['wounds'] == 0:
                finished = True
            if len(current_fighter['hits']) == 0 and len(opponent['hits']) == 0:
                finished = True
            current_fighter, opponent = opponent, current_fighter
        return ((attacker['name'], attacker['wounds']), (defender['name'], defender['wounds']))


# library
import seaborn as sns
import pandas as pd
import numpy as np
import itertools

# Create a dataset
#df = pd.DataFrame(matrix, columns=["a","b","c","d","e"])
 
# Default heatmap: just a visualization of this square matrix
#sns.heatmap(df)

class WeaponDamageProfile(object):
    
    def __init__(self, weapon):
        self.weapon = weapon
        
    def generate_matrix(self, accumulated=True):
        target_probs = []
        columns = []
        targets = [
            Target(3,3),
            #Target(3,3, wounds=14),
            Target(3,4),
            #Target(3,4, wounds=10),
            Target(3,5),
            #Target(3,5, wounds=7),
            #Target(3,5, wounds=19, ignore_wounds_on=5),
            #Target(3,5, wounds=7, ignore_wounds_on=6)
        ]
        target_wounds = [x.wounds for x in targets]
        max_damage = (self.weapon.cd + self.weapon.mw) * self.weapon.attacks + 1
        num_rows = (max_damage) if 0 in target_wounds else (max(target_wounds) + 1)
        for target in targets:
            last = ['', '', '', '']
            for cover_save, save_reroll, attack_reroll in itertools.product(range(1,-1, -1), range(1,-1, -1), range(3)):
                # max damage is all crits or wound limit based on targets
                base = [0] * num_rows
                scenario = self.weapon.shoot(
                    target,
                    save_rerolls=save_reroll,
                    attack_rerolls=attack_reroll,
                    cover=cover_save
                )
                for (wounds, prob) in list(scenario.pmf_tuple):
                    base[wounds] = prob * 100
                if accumulated:
                    for (wounds, prob) in reversed(list(enumerate(base))):
                        if wounds < len(base) - 1:
                            base[wounds] = base[wounds + 1] + base[wounds]
                target_probs.append(base)
                current = [
                    str(target),
                    'has cover,' if cover_save == 1 else 'has no cover,' if cover_save == 0 else '{} cover,'.format(cover_save),
                    'defense reroll,' if save_reroll == 1 else 'no defense reroll,' if save_reroll == 0 else '{} defense rerolls,'.format(save_reroll),
                    'no attack reroll' if attack_reroll == 0 else '{} attack rerolls'.format(attack_reroll),
                ]
                diff = [ c if c != l else '' for (c, l) in zip(current, last)]
                columns.append(' '.join(diff))
                last = current
            base = [0] * num_rows
            target_probs.append(base)
            columns.append('------')
        target_probs.pop()
        columns.pop()
        return (target_probs, columns)

from matplotlib import rcParams

# figure size in inches
rcParams['figure.figsize'] = [14, 10]

def plot_heatmap(weapon, accumulated=True):
    probs, columns = WeaponDamageProfile(weapon).generate_matrix(accumulated)
    rcParams['figure.figsize'] = [len(columns)/3 + 1, len(probs)/8 + 1.5]
    df = pd.DataFrame(np.transpose(probs), columns=columns)
    ax = sns.heatmap(df, square=False, annot=True, fmt='.0f')
    #ax = sns.heatmap(df, square=False, annot=False, fmt='.0f')
    ax.invert_yaxis()
    ax.set_title('{} - prob to cause X damage {}'.format(weapon.name, 'or more' if accumulated else ''))

def survives_or_not(wounds, fighter):
    if wounds == 0:
        return 'dead'
    else:
        return 'survives'

def op_state(wounds, fighter):
    if wounds == 0:
        return 'dead'
    if wounds < int(fighter.wounds / 2):
        return 'injured'
    if wounds == fighter.wounds:
        return 'untouched'
    else:
        return 'survives'
    
    
def kill_or_not(result, attacker, defender, show_state=False):
    ar, dr = result
    func = op_state if show_state else survives_or_not
    return '(D) {} {} - (A) {} {}'.format(
        defender.name,
        func(dr[1], defender),
        attacker.name,
        func(ar[1], attacker)
    )


def describe_combat_result(x):
    return '(D) {} ({:0>2}) vs (A) {} ({:0>2})'.format(x[1][0],x[1][1], x[0][0], x[0][1])


def print_combat_results(fight):
    attacker_rerolls = 1
    defender_rerolls = 1
    combat_probs = fight.fight(attacker_rerolls, defender_rerolls)
    print('Combat Results:\n--------------')
    print('attacker rerolls: {}\n'.format(attacker_rerolls))
    print('defender rerolls: {}\n'.format(defender_rerolls))
    print('Survibability:\n')
    probs = combat_probs.map(lambda x: kill_or_not(x, fight.attacker, fight.defender))
    print(probs.as_string('%-',nb_decimals=2))
    print('\nOperative state:\n')
    probs = combat_probs.map(lambda x: kill_or_not(x, fight.attacker, fight.defender, True))
    print(probs.as_string('%-',nb_decimals=2))
    print('\nFull Probs:\n')
    probs = combat_probs.map(describe_combat_result)
    print(probs.as_string('%-',nb_decimals=2))



#apply_damage(KtRoll(4).roll(3, rerolls=1),2, 3).plot()
#apply_damage(KtRoll(3).roll(4, rerolls=1),5, 6).plot()

#plasma = Weapon('Plasma - Supercharge', 4, 3, 5, 6, ['AP2', 'Hot'])
#plasma.plot_shoot(Target(3,3), attack_rerolls=0, cover=1)
#plasma.plot_shoot(Target(3,3), attack_rerolls=0, cover=0)
