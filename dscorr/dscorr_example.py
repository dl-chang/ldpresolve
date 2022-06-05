import os

import numpy as np

import domain_embedding
import dscorr

################ read data from files ####################

def domain2index(domain_vectors, domain_dict):
    '''Convert domain counter to arrays of words and weights, which is used as session data in our method.'''
    words = []
    weights = []
    for domain, weight in domain_dict.items():
        word = domain_vectors.key_to_index.get(domain, None)
        if word is None:
            continue
        words.append(word)
        weights.append(weight)
    return np.array([words, weights], dtype=np.uint32)


def read_domain_dict(fin):
    '''Read a DNS session file and return counter dictionary of domains.'''
    domain_dict = {}
    for line in fin:
        d = line.rstrip('\n')
        domain_dict[d] = domain_dict.get(d, 0) + 1
    return domain_dict


def file_to_session(domain_vectors, fin):
    '''Read a DNS session file. One domain per line.'''
    domain_dict = read_domain_dict(fin)
    return domain2index(domain_vectors, domain_dict)

def read_data_user(domain_vectors, root):
    '''Read all DNS sessions of a same user, which saved in a same folder.'''
    user_session_list = []
    for f in os.listdir(root):
        fpath = os.path.join(root, f)
        with open(fpath, 'r') as fin:
            ww = file_to_session(domain_vectors, fin)
        user_session_list.append(ww)
    return user_session_list

def read_data(domain_vectors, root):
    '''Read session data from all users.'''
    WORDS_N_WEIGHTS = []
    for user in os.listdir(root):
        user_session_list = read_data_user(domain_vectors, os.path.join(root, user))
        WORDS_N_WEIGHTS.append(user_session_list)
    return WORDS_N_WEIGHTS

def select_test_sessions(words_n_weights, n):
    '''Choose first n sessions of a same user as labeled sessions, the other sessions are seen as unlabeled sessions for test.'''
    labeled_ww = []
    unlabeled_ww_list = []
    for uix, user_session_list in enumerate(words_n_weights):
        labeled_ww.append(user_session_list[:n])
        for ww in user_session_list[n:]:
            unlabeled_ww_list.append({
                'uid': uix,
                'ww': ww
            })
    return labeled_ww, unlabeled_ww_list

###############################################


def main():
    '''Example: Test a list of unlabeled sessions.'''

    DOMAIN_VECTORS = domain_embedding.load_model('path/to/domain/embedding/model')
    WORDS_N_WEIGHTS = read_data(DOMAIN_VECTORS, 'path/to/dns/session/data')    # eg, sample/dns_session
    LABELED_WW, UNLABELED_WW = select_test_sessions(WORDS_N_WEIGHTS, 10)

    ####### closed-world settings #######
    # ds = dscorr.DSCorrClosed()
    # ds.set(KNOWN_WW, DOMAIN_VECTORS)

    ####### open-world settings #######
    ds = dscorr.DSCorrOpen()
    ds.set(LABELED_WW, DOMAIN_VECTORS, theta=1)

    for t in UNLABELED_WW:
        ds.test_single_session(t, num_nearest=50, prt=True)  # test sessions, print result detail.

if __name__ == '__main__':
    main()
