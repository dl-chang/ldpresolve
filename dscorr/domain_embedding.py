import gensim
import os

class DomainSentence(object):
    '''Convert DNS log to sentences of domain names.'''
    def __init__(self, de_duplicate, max_interval, max_len):
        self.seq = []
        self._de_duplicate = de_duplicate
        self._max_interval = max_interval
        self._max_len = max_len

    @staticmethod
    def process_line(line):
        '''Format input lines.'''
        timestr, domain = line.split(' ')
        return float(timestr), domain.rstrip('\n')

    @property
    def _last_t(self):
        '''Last timestamp.'''
        return self.seq[-1][0]

    @property
    def _last_domain(self):
        '''Last domain name.'''
        return self.seq[-1][1]

    @property
    def _consecutive_interval(self):
        '''Interval of last two domains.'''
        return self.seq[-1][0] - self.seq[-2][0]

    @property
    def _seq_len(self):
        '''Time span of domain sequence.'''
        return self.seq[-1][0] - self.seq[0][0]

    def add_line(self, line):
        '''Process one line.'''
        t, domain = self.process_line(line)
        if not self.seq:
            self.seq.append((t, domain))
            return self.check_sentence_flag()

        if self._de_duplicate and domain == self._last_domain:
            return self.check_sentence_flag()

        self.seq.append((t, domain))
        return self.check_sentence_flag()

    def check_sentence_flag(self):
        '''Check if there's a complete sentence.'''
        if len(self.seq) < 2:
            return False
        if self._consecutive_interval > self._max_interval:
            return True
        if self._seq_len > self._max_len:
            return True
        return False
        
    def get_sentence(self):
        '''Get the generated sentence.'''
        if len(self.seq) < 2:
            sentence = [d for (t,d) in self.seq]
            self.seq = []
            return sentence
        if self._consecutive_interval > self._max_interval:
            sentence = [d for (t,d) in self.seq[:-1]]
            self.seq = self.seq[-1:]
            return sentence
        if self._seq_len > self._max_len:
            mid_time = (self.seq[0][0] + self.seq[-1][0]) / 2
            i = 0
            while self.seq[i][0] < mid_time:
                i += 1
            sentence = [d for (t,d) in self.seq[:i]]
            self.seq = self.seq[i:]
            return sentence
        sentence = [d for (t,d) in self.seq]
        self.seq = []
        return sentence

class DomainSentenceGen(DomainSentence):
    '''Iterator of sentence generation.'''
    def __init__(self, path, de_duplicate=True, max_interval = 300, max_len = 7200):
        super().__init__(de_duplicate, max_interval, max_len)
        self._path = path
        
    def __iter__(self):
        '''Iteration function.'''
        for fname in os.listdir(self._path):
            with open(os.path.join(self._path, fname), 'r') as f:
                for line in f:
                    sentence_flag = self.add_line(line)
                    if sentence_flag:
                        yield self.get_sentence()
            yield self.get_sentence()


def word2vec_train(dns_path, model_path, dns_log_params, w2v_params):
    '''Train a domain embedding model based on word2vec model.
    
    Parameters:
        dns_path(str): Root dir of DNS logs.
        model_path(str): Output path of the trained domain embedding model.
        dns_log_params(dict): Parameters of domain sequence generation:
            'de_duplicate'(bool): If true, ignore consecutive duplicate domain names.
            'max_interval'(int): If the interval of two consecutive domains is greater than max_interval, the domains will be treated as two sentences.
            'max_len'(int): The maximum domain sequence time span allowed for a sentence.
        w2v_params(dict): Parameters of word2vector model training. See https://radimrehurek.com/gensim/models/word2vec.html

    Returns:
        None
    '''
    sentences = DomainSentenceGen(dns_path, **dns_log_params)
    model = gensim.models.Word2Vec(sentences, **w2v_params)
    model.save(model_path)

def load_model(model_path):
    '''Takes in model_path, load domain embedding model.
    
    Parameters:
        model_path(str): Path of the trained domain embedding model.

    Returns:
        domain_vectors(gensim.models.keyedvectors.KeyedVectors): word vectors of domain embedding model
    '''
    _wv = gensim.models.KeyedVectors.load(model_path)
    domain_vectors = _wv.wv
    return domain_vectors


            