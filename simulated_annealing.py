"""
Simulated Annealing ile yönlendirme.

Başlangıç çözümü: bant genişliği filtrelenmiş grafta en az atlamalı yol.
Komşu çözüm: bir ara düğümü silmek, ortak komşuyla değiştirmek, yeni düğüm eklemek,
rastgele bir düğüm üzerinden yeniden kurmak ya da iki ara düğümün yerini değiştirmek;
ardından yol onarılır.
Daha kötü bir çözüm exp(-Δ/T) olasılıkla kabul edilir; sıcaklık her adımda soğutulur.
"""
import math
import random
from typing import Dict, List, Tuple

import networkx as nx

from genetik_algoritma import repair_path


class SimulatedAnnealing:
    """Kaynak-hedef arasında en düşük ağırlıklı maliyetli yolu arar."""

    def __init__(self, ortam, source: int, destination: int, istenen_bw: float,
                 initial_temp: float = 10.0, cooling_rate: float = 0.95,
                 num_iterations: int = 100, iterations_per_temp: int = 10):
        """
        ortam              : network_model.AgOrtami (maliyet hesabı için)
        initial_temp       : başlangıç sıcaklığı (fitness birimiyle aynı ölçekte)
        cooling_rate       : her sıcaklık adımında T = T * cooling_rate
        num_iterations     : sıcaklık adımı sayısı
        iterations_per_temp: her sıcaklıktaki deneme sayısı
        """
        self.ortam = ortam
        self.graph = ortam.filtrele(istenen_bw)
        self.istenen_bw = istenen_bw
        self.source = source
        self.destination = destination
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
        self.num_iterations = num_iterations
        self.iterations_per_temp = iterations_per_temp

    def _cost(self, path: List[int]) -> float:
        return self.ortam.yol_maliyeti_hesapla(path, self.istenen_bw)[0]

    def _get_neighbor(self, current_path: List[int]) -> List[int]:
        """Mevcut yolu rastgele bir değişiklikle bozup onarır."""
        new_path = current_path[:]
        move = random.randint(0, 4)

        if move == 0 and len(new_path) > 2:
            # Bir ara düğümü sil
            new_path.pop(random.randint(1, len(new_path) - 2))
        elif move == 4 and len(new_path) > 2:
            # Bir ara düğümü, önceki ve sonraki düğümün ortak komşusuyla değiştir (yol geçerli kalır)
            i = random.randint(1, len(new_path) - 2)
            common = (set(self.graph.neighbors(new_path[i - 1])) & set(self.graph.neighbors(new_path[i + 1]))) - set(new_path)
            if common:
                new_path[i] = random.choice(sorted(common))
        elif move == 1:
            # Bir düğümden sonra onun komşularından birini ekle
            idx = random.randint(1, len(new_path) - 1)
            candidates = [n for n in self.graph.neighbors(new_path[idx - 1]) if n not in new_path]
            if candidates:
                new_path.insert(idx, random.choice(candidates))
        elif move == 2 and len(new_path) > 3:
            # Bir bölümü rastgele bir ara düğüm üzerinden yeniden kur
            i = random.randint(1, len(new_path) - 2)
            new_path = new_path[:i] + [random.choice(list(self.graph.nodes))] + new_path[i + 1:]
        elif len(new_path) > 3:
            # İki ara düğümün yerini değiştir
            i, j = random.sample(range(1, len(new_path) - 1), 2)
            new_path[i], new_path[j] = new_path[j], new_path[i]

        repaired = repair_path(self.graph, new_path, self.source, self.destination)
        return repaired if repaired else current_path[:]

    def optimize(self) -> Tuple[List[int], float, Dict]:
        """(en_iyi_yol, en_iyi_maliyet, geçmiş) döndürür; geçerli yol yoksa ([], inf, {})."""
        try:
            current_path = nx.shortest_path(self.graph, self.source, self.destination)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return [], float('inf'), {}
        current_cost = self._cost(current_path)
        best_path, best_cost = current_path[:], current_cost

        temperature = self.initial_temp
        history = {'best_cost': [], 'current_cost': [], 'temperature': []}

        for _ in range(self.num_iterations):
            for _ in range(self.iterations_per_temp):
                new_path = self._get_neighbor(current_path)
                new_cost = self._cost(new_path)
                delta = new_cost - current_cost
                if delta < 0 or random.random() < math.exp(-delta / temperature):
                    current_path, current_cost = new_path, new_cost
                    if current_cost < best_cost:
                        best_path, best_cost = current_path[:], current_cost

            temperature *= self.cooling_rate
            history['best_cost'].append(best_cost)
            history['current_cost'].append(current_cost)
            history['temperature'].append(temperature)

        return best_path, best_cost, history
