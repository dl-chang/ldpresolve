from collections import Counter

import numpy as np

class DSCorrClosed(object):
    '''DSCorr closed-world settings'''
    @staticmethod
    def merge_sessions(user_session_list):
        '''Merge sessions of a same user to get a summary of sessions'''
        merged_dict = {}
        for ww in user_session_list:
            words, weights = ww
            for i in range(len(words)):
                merged_dict[words[i]] = merged_dict.get(words[i], 0) + weights[i]
        words = []
        weights = []
        for word, weight in merged_dict.items():
            words.append(word)
            weights.append(weight)
        return np.array([words, weights], dtype=np.uint32)

    def merge_train_ww(self, train_ww):
        return [self.merge_sessions(user_session_list) for user_session_list in train_ww]

    def set(self, train_ww, word_vectors):
        '''Set labeled sessions and domain embedding model

        Parameters:
            train_ww: Labeled sessions. Array of array. Each element is session list of a single user.
            word_vectors(gensim.models.keyedvectors.KeyedVectors): Domain embedding model trained by gensim
        '''
        self.train_ww = train_ww
        self.merged_ww = self.merge_train_ww(train_ww)
        self.word_vectors = word_vectors
        self.normed_wv = word_vectors.get_normed_vectors()
        self.idf_list = self.generate_global_idf()

    def generate_global_idf(self):
        '''Generate inverse document frequency.'''
        global_domain_counter = Counter()
        session_count = 0
        for ww_user in self.train_ww:
            for words, _ in ww_user:
                global_domain_counter.update(words)
            session_count += len(ww_user)
        global_idf = [ 1 for i in range(len(self.word_vectors))]
        for i in global_domain_counter:  # not all domain is appeared
            global_idf[i] = np.log(session_count/global_domain_counter[i])
        return global_idf

    def text_sim(self, words1, weights1, words2, weights2, tf=False):
        '''Takes in words and weights of two sessions, calculate their similarity.'''
        wv_matrix_1 = self.normed_wv[words1]
        wv_matrix_2 = self.normed_wv[words2]

        dist_matrix = wv_matrix_1.dot(wv_matrix_2.T)
        word_sim_1to2 = dist_matrix.max(axis=1)
        word_sim_2to1 = dist_matrix.max(axis=0)
        
        idf_coeff_1 = np.array([self.idf_list[wi] for wi in words1])
        idf_coeff_2 = np.array([self.idf_list[wi] for wi in words2])
        if tf is True:
            idf_coeff_1 *= weights1
            idf_coeff_2 *= weights2
        
        async_doc_sim_1to2 = word_sim_1to2.dot(idf_coeff_1) / idf_coeff_1.sum()
        async_doc_sim_2to1 = word_sim_2to1.dot(idf_coeff_2) / idf_coeff_2.sum()

        return (async_doc_sim_1to2 + async_doc_sim_2to1) / 2

    def test_session_to_session(self, session1, session2, tf=True):
        '''Takes in two sessions, calculate session to session similarity.'''
        words1, weights1 = session1
        words2, weights2 = session2
        return self.text_sim(words1, weights1, words2, weights2, tf=tf)

    def test_single_session_to_user_detail(self, train_uix, test_session, tf=True):
        '''Calculate the distance between an unlabeled session to every lableled session of a user.'''
        sims = []
        for ww_session in self.train_ww[train_uix]:
            sim = self.test_session_to_session(ww_session, test_session, tf=tf)
            sims.append(sim)
        return 1 - np.array(sims)

    def phase_one(self, test_session, num_nearest):
        '''Takes in num_nearest, get num_nearest candidate users (step3 in our paper)'''
        sims = []
        for ww in self.merged_ww:
            sim = self.test_session_to_session(ww, test_session, tf=True)
            sims.append(sim)
        return np.argsort(sims)[-num_nearest:]

    @staticmethod
    def choose_function(x):
        return np.min(x)

    def phase_two(self, nearest_users, test_session):
        '''Find nearest user (step4 in our paper)'''
        results = []
        for uix in nearest_users:
            dists = self.test_single_session_to_user_detail(uix, test_session, tf=True)
            results.append((uix, self.choose_function(dists)))
        return min(results, key=lambda x:x[1])

    def test_single_session(self, test_session_dict, num_nearest, prt=False):
        '''Identify the user of a given session. 
        
        Parameters:
            test_session_dict(dict): Data of test session. 
                'uid': Real user id, only used in print function. 
                'ww'(numpy.array[2,n]): words and weights of test session. 
            num_nearest(int): number of nearest users are chosen as candidate users.
            prt(bool): If true, print detailed identification result.

        Returns:
            uix(int): Predicted user index.
        '''
        nearest_users = self.phase_one(test_session_dict['ww'], num_nearest)
        uix, dist = self.phase_two(nearest_users, test_session_dict['ww'])
        if prt:
            print(f'real:{test_session_dict["uid"]}, predict:{uix}, dist:{dist:.3f}')
        return uix

class AutoThreshold(object):
    '''Auto threshold calculation. A intermediate class used for open-world setting.'''
    def __init__(self):
        self.dat = {}

    def add(self, uix, dists_mat):
        self.dat[uix] = dists_mat

    def get(self, uix):
        return self.dat.get(uix, None)

    def get_tsd_one_user(self, uix, choose_function=np.min):
        dists_stat = []
        ww_dists_mat = self.get(uix)
        for session_id, dists in enumerate(ww_dists_mat):
            stat_one_session = choose_function(np.delete(dists, session_id))
            dists_stat.append(stat_one_session)
        return dists_stat

    def get_threshold(self, uix, choose_function, theta=1):
        stat_self = self.get_tsd_one_user(uix, choose_function=choose_function)
        if theta > 1:
            return (theta-1) * (max(stat_self)-min(stat_self)) + max(stat_self)
        return np.quantile(stat_self, theta)

class DSCorrOpen(DSCorrClosed):
    '''DSCorr open-world settings'''
    @staticmethod
    def choose_function(x):
        return np.quantile(x, 0.25)

    def get_self_dists_one_user(self, user_session_list):
        '''Get self distance matrix of a user.'''
        dist_mat = np.zeros((len(user_session_list), len(user_session_list)))
        for i, ww_1 in enumerate(user_session_list[:-1]):
            for j in range(i+1, len(user_session_list)):
                d = 1 - self.test_session_to_session(ww_1, user_session_list[j], tf=True)
                dist_mat[i][j] = d
                dist_mat[j][i] = d
        return dist_mat

    def get_thresholds(self, theta):
        threshold_list = []
        for uix in range(len(self.train_ww)):
            t = self.auto_threshold.get_threshold(uix, self.choose_function, theta)
            threshold_list.append(t)
        return threshold_list

    def set_thresholds(self, theta):
        '''Takes in theta, generate threshold t for each user.'''
        self.threshold_list = self.get_thresholds(theta)

    def set(self, train_ww, word_vectors, theta=1):
        '''Set labeled sessions, domain embedding model and thresholds.

        Parameters:
            train_ww: Labeled sessions. Array of array. Each element is session list of a single user.
            word_vectors(gensim.models.keyedvectors.KeyedVectors): Domain embedding model trained by gensim.
            theta(float or int): parameter to generate thereshold t (see paper).
        '''
        super().set(train_ww, word_vectors)
        self.auto_threshold = AutoThreshold()
        for uix, user_session_list in enumerate(self.train_ww):
            dist_mat = self.get_self_dists_one_user(user_session_list)
            self.auto_threshold.add(uix, dist_mat)
        self.set_thresholds(theta)


    def test_single_session(self, test_session_dict, num_nearest, prt=False):
        '''Identify the user of a given session in open-world setting. Will return None if the session is identified as "unknown".

        Parameters:
            test_session_dict(dict): Data of test session. 
                'uid': Real user id, only used in print function. 
                'ww'(numpy.array[2,n]): words and weights of test session. 
            num_nearest(int): number of nearest users are chosen as candidate users.
            prt(bool): If true, print detailed identification result.

        Returns:
            uix(int or None): Predicted user index. None if labeled as "unknown".
        '''
        nearest_users = self.phase_one(test_session_dict['ww'], num_nearest)
        uix, dist = self.phase_two(nearest_users, test_session_dict['ww'])
        t = self.threshold_list[uix]
        if prt:
            print(f'label:{test_session_dict["uid"]}, predict:{uix}, known:{t>dist}, t:{t:.3f}, dist:{dist:.3f}')
        if dist < t:
            return uix
        return None

