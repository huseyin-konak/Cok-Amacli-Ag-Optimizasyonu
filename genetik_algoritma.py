"""
Genetik Algoritma ile yönlendirme.

Birey: kaynaktan hedefe giden bir yol (düğüm listesi).
Başlangıç popülasyonu: bant genişliği filtrelenmiş grafta rastgele yürüyüşle üretilen yollar.
Seçim: turnuva; elitizm: en iyi %10 doğrudan aktarılır.
Çaprazlama: tek noktalı; mutasyon: ara düğümü atlama, ortak komşuyla değiştirme ya da yer değiştirme.
Çaprazlama/mutasyon sonrası kopan bağlantılar en kısa yolla onarılır ve oluşan döngüler kesilir.
"""
import random

import networkx as nx

from network_model import AgOrtami


def random_valid_path(graph, S, D, max_len=80):
    """S'den D'ye döngüsüz rastgele bir yol; bulunamazsa None."""
    path, visited, current = [S], {S}, S
    for _ in range(max_len):
        if current == D:
            return path
        candidates = [n for n in graph.neighbors(current) if n not in visited]
        if not candidates:
            return None
        current = random.choice(candidates)
        visited.add(current)
        path.append(current)
    return None


def remove_loops(path):
    """Yolda tekrar eden bir düğüm varsa aradaki döngüyü keser: [1,2,3,2,4] -> [1,2,4]."""
    result, index = [], {}
    for node in path:
        if node in index:
            cut = index[node]
            for removed in result[cut + 1:]:
                index.pop(removed, None)
            result = result[:cut + 1]
        else:
            index[node] = len(result)
            result.append(node)
    return result


def repair_path(graph, path, S, D):
    """Kopuk bağlantıları en kısa yolla birleştirir, döngüleri keser; onarılamazsa None."""
    if not path:
        return None
    if path[0] != S:
        path = [S] + path
    if path[-1] != D:
        path = path + [D]

    repaired = [path[0]]
    for v in path[1:]:
        u = repaired[-1]
        if u == v:
            continue
        if graph.has_edge(u, v):
            repaired.append(v)
        else:
            try:
                repaired.extend(nx.shortest_path(graph, u, v)[1:])
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                return None
    return remove_loops(repaired)


def tournament_selection(population, fitness, k=5):
    group = random.sample(population, min(k, len(population)))
    return min(group, key=lambda p: fitness[tuple(p)])


def elitism(population, fitness, rate=0.1):
    elite_n = max(1, int(len(population) * rate))
    return [p.copy() for p in sorted(population, key=lambda p: fitness[tuple(p)])[:elite_n]]


def crossover(p1, p2):
    """Tek noktalı çaprazlama (çocuklar repair_path ile geçerli hale getirilir)."""
    if len(p1) < 3 or len(p2) < 3:
        return p1[:], p2[:]
    c1 = random.randint(1, len(p1) - 2)
    c2 = random.randint(1, len(p2) - 2)
    return p1[:c1] + p2[c2:], p2[:c2] + p1[c1:]


def mutate(graph, path, rate=0.2):
    """
    rate olasılıkla üç mutasyondan biri uygulanır:
    bir ara düğümü atlamak (yolu kısaltır), bir ara düğümü önceki ve sonraki düğümün
    ortak komşusuyla değiştirmek ya da iki ara düğümün yerini değiştirmek.
    """
    if random.random() >= rate or len(path) < 3:
        return path
    i = random.randint(1, len(path) - 2)
    kind = random.randint(0, 2)
    if kind == 0:
        return path[:i] + path[i + 1:]
    if kind == 1:
        common = (set(graph.neighbors(path[i - 1])) & set(graph.neighbors(path[i + 1]))) - set(path)
        if common:
            path[i] = random.choice(sorted(common))
        return path
    if len(path) > 3:
        i, j = random.sample(range(1, len(path) - 1), 2)
        path[i], path[j] = path[j], path[i]
    return path


def genetic_algorithm(ortam, S, D, bw, pop_size=50, generations=100):
    """En iyi yolu ve maliyetini döndürür; geçerli yol yoksa (None, inf)."""
    graph = ortam.filtrele(bw)
    if S not in graph or D not in graph:
        return None, float('inf')

    population, attempts = [], 0
    while len(population) < pop_size and attempts < pop_size * 10:
        p = random_valid_path(graph, S, D)
        if p:
            population.append(p)
        attempts += 1
    if not population:
        return None, float('inf')

    def evaluate(pop):
        return {tuple(p): ortam.yol_maliyeti_hesapla(p, istenen_bw=bw)[0] for p in pop}

    fitness = evaluate(population)
    best_path, best_cost = None, float('inf')

    for _ in range(generations):
        elites = elitism(population, fitness)
        if fitness[tuple(elites[0])] < best_cost:
            best_path, best_cost = elites[0].copy(), fitness[tuple(elites[0])]

        new_population = list(elites)
        while len(new_population) < pop_size:
            p1 = tournament_selection(population, fitness)
            p2 = tournament_selection(population, fitness)
            c1, c2 = crossover(p1, p2)
            for child in (repair_path(graph, mutate(graph, c1), S, D), repair_path(graph, mutate(graph, c2), S, D)):
                if child and len(new_population) < pop_size:
                    new_population.append(child)

        population = new_population
        fitness = evaluate(population)

    # Son neslin en iyisi de değerlendirilir
    last_best = min(population, key=lambda p: fitness[tuple(p)])
    if fitness[tuple(last_best)] < best_cost:
        best_path, best_cost = last_best.copy(), fitness[tuple(last_best)]

    return best_path, best_cost


if __name__ == "__main__":
    ortam = AgOrtami()
    ortam.verileri_yukle_ve_agi_kur()
    talep = ortam.talep_listesini_getir()[0]

    best_path, best_cost = genetic_algorithm(ortam, talep["kaynak"], talep["hedef"], talep["miktar"])
    if best_path:
        print(f"En iyi yol ({len(best_path)} düğüm): {best_path}")
        print(f"Fitness: {best_cost:.4f}")
    else:
        print("Uygun bir yol bulunamadı.")
