"""
Q-Learning ile yönlendirme.

Durum: ajanın bulunduğu düğüm. Eylem: bir komşu düğüme geçmek.
Ödül: geçilen bağlantının ve girilen düğümün ağırlıklı maliyetinin negatifi
(network_model ile aynı ağırlıklar). Hedefe ulaşınca +5, daha önce ziyaret edilmiş
bir düğüme dönmek (döngü) -1000 ve bölüm sonu.
Yalnızca istenen bant genişliğini karşılayan bağlantılar kullanılır.
"""
import math
import random
import time

import numpy as np

import network_model


class NetworkRoutingEnv:
    """Yönlendirme ortamı: bant genişliği filtrelenmiş graf üzerinde adım adım ilerleme."""

    def __init__(self, ortam, source, target, bandwidth_demand):
        self.G = ortam.filtrele(bandwidth_demand)
        self.weights = (ortam.w_gecikme, ortam.w_guvenilirlik, ortam.w_kaynak)
        self.source = source
        self.target = target
        self.reset()

    def reset(self):
        """Her bölüm (episode) başında ajanı kaynak düğüme döndürür."""
        self.state = self.source
        self.path_history = [self.source]
        self.visited = {self.source}
        return self.state

    def calculate_reward(self, action):
        """Bulunulan düğümden 'action' düğümüne geçişin ödülü (maliyetin negatifi)."""
        edge = self.G.edges[self.state, action]
        node = self.G.nodes[action]
        delay = edge['gecikme'] + (0.0 if action == self.target else node['islem_suresi'])
        reliability = -math.log(edge['guvenilirlik']) - math.log(node['guvenilirlik'])
        bw_cost = 1000.0 / edge['bant_genisligi']
        w_d, w_r, w_b = self.weights
        return -(w_d * delay + w_r * reliability + w_b * bw_cost)

    def step(self, action):
        """Bir komşuya geçer. Döndürür: (yeni_durum, ödül, bölüm_bitti_mi)."""
        if action in self.visited:
            return self.state, -1000.0, True      # döngü: ağır ceza, bölüm biter

        reward = self.calculate_reward(action)
        self.state = action
        self.path_history.append(action)
        self.visited.add(action)

        if self.state == self.target:
            return self.state, reward + 5.0, True
        return self.state, reward, False


def q_learning_egit(env, episode, epsilon, epsilon_min, epsilon_decay, alpha, gamma, max_steps):
    """
    Q tablosunu epsilon-greedy keşifle eğitir ve döndürür.
    epsilon 1'den büyük verilirse ilk bölümler tamamen rastgele keşifle geçer
    (epsilon her bölüm sonunda epsilon_decay ile çarpılarak azalır).
    """
    env.reset()
    max_id = max(env.G.nodes) if len(env.G) else 0
    q_table = np.zeros((max_id + 1, max_id + 1))

    # Komşu listeleri bir kez hesaplanır (her adımda grafa sormaktan çok daha hızlı)
    komsular = {node: list(env.G.neighbors(node)) for node in env.G.nodes}

    print(">> Q-Learning eğitimi başlıyor...")
    t1 = time.time()
    for _ in range(episode):
        state = env.reset()
        done = False
        steps = 0

        while not done and steps < max_steps:
            neighbors = komsular.get(state, [])
            if not neighbors:
                action = state                     # çıkmaz: step() döngü cezası verir
            elif env.target in neighbors and random.random() < 0.5:
                action = env.target                # hedef komşuysa keşfi hızlandırmak için sık dene
            elif random.random() < epsilon:
                action = random.choice(neighbors)  # keşif
            else:
                action = neighbors[int(np.argmax([q_table[state, n] for n in neighbors]))]  # sömürü

            next_state, reward, done = env.step(action)

            # Bölüm bittiyse (hedef ya da döngü) gelecekten değer eklenmez
            if done:
                target_q = reward
            else:
                next_neighbors = komsular.get(next_state, [])
                max_future_q = max(q_table[next_state, n] for n in next_neighbors) if next_neighbors else -1000.0
                target_q = reward + gamma * max_future_q

            q_table[state, action] += alpha * (target_q - q_table[state, action])
            state = next_state
            steps += 1

        if epsilon > epsilon_min:
            epsilon *= epsilon_decay

    print(f">> Q-Learning eğitimi bitti ({time.time() - t1:.2f} sn)")
    return q_table


def q_learning_calistir(env, q_table, max_steps):
    """Eğitilmiş Q tablosuyla açgözlü (greedy) rota çıkarır. Hedefe ulaşılamazsa None döner."""
    curr = env.reset()
    path = [curr]
    for _ in range(max_steps):
        neighbors = [n for n in env.G.neighbors(curr) if n not in env.visited]
        if not neighbors:
            return None
        action = neighbors[int(np.argmax([q_table[curr, n] for n in neighbors]))]
        curr, _, done = env.step(action)
        path.append(curr)
        if done:
            return path if curr == env.target else None
    return None


if __name__ == "__main__":
    ag = network_model.AgOrtami()
    ag.verileri_yukle_ve_agi_kur()
    talep = ag.talep_listesini_getir()[1]

    env = NetworkRoutingEnv(ag, talep['kaynak'], talep['hedef'], talep['miktar'])
    q_table = q_learning_egit(env, episode=1500, epsilon=2.0, epsilon_min=0.1, epsilon_decay=0.998,
                              alpha=0.5, gamma=0.9, max_steps=50)
    path = q_learning_calistir(env, q_table, max_steps=50)
    print(f"Rota: {path}")
    print(f"Yol maliyeti: {ag.yol_maliyeti_hesapla(path, talep['miktar'])}")
