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

    def __init__(self, df, sv, ignore_wounds_on=0, wounds=0):
        self.df = df
        self.sv = sv
        self.ignore_wounds_on = ignore_wounds_on
        self.wounds = wounds

    def save(self):
        return KtRoll(self.sv)

    def get_defense(self):
        return self.df

    def __str__(self):
        return 'Sv: {} Df: {}{}'.format(self.sv, self.df, '' if self.ignore_wounds_on == 0 else ' ignore wounds on {}+'.format(self.ignore_wounds_on))


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

#apply_damage(KtRoll(4).roll(3, rerolls=1),2, 3).plot()
#apply_damage(KtRoll(3).roll(4, rerolls=1),5, 6).plot()

#plasma = Weapon('Plasma - Supercharge', 4, 3, 5, 6, ['AP2', 'Hot'])
#plasma.plot_shoot(Target(3,3), attack_rerolls=0, cover=1)
#plasma.plot_shoot(Target(3,3), attack_rerolls=0, cover=0)
