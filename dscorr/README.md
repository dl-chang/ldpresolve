# DNS-based User Tracking
## Dependencies
Codes are written in Python 3.

* `gensim` is used to train domain embedding model.
* `numpy` is used for fast computing.

## Domain Embedding Model

Train a domain embedding model with DNS logs. 
Log does not need to be labeled. Sample data is in folder `sample/dnslog/`, one IP per file.

Example of training the embedding model:

```python
import domain_embedding

domain_embedding.word2vec_train(
        dns_path='path/to/dns/logs',                  # eg, sample/dns_log
        model_path='path/to/domain/embedding/model',  # output model path
        dns_log_params={                              # Parameters of domain sequence generation
            'de_duplicate': True,                     # If true, ignore consecutive duplicate domain names.
            'max_interval': 300,                      # If the interval of two consecutive domains is greater than max_interval, 
                                                      # the domains will be treated as two sentences.
            'max_len': 7200                           # The maximum domain sequence time span allowed for a sentence.
        },
        w2v_params={                                  # Parameters of word2vector model training. See https://radimrehurek.com/gensim/models/word2vec.html
            'sg': 1,
            'sample': 1e-5,
            'negative': 5,
            'vector_size': 200,
            'window': 10,
            'min_count':5,
            'workers': 16,
        })
```

After training, the model could be used in DSCorr tracking or other tasks.

Example of finding the most similar domain names of a given domain:

```python
import domain_embedding

model = domain_embedding.load_model('path/to/domain/embedding/model')
d = 'www.example.com'
print(f'most similar domain of {d}:')
for sim_d, sim_v in model.most_similar(d):
    print(f'{sim_v:.3f},  {sim_d}')
```

See `domain_embedding_example.py` for examples.

See `domain_embedding.py` for more details of domain embedding model.


## DSCorr: DNS-based User Tracking
After obtaining the domain embedding model, we can track a user with his/her previous DNS queries. 
A simple example of data is located in folder `sample/dns_session/`.
One user per subfolder, such as `sample/dns_session/0/`.
One session per file, such as `sample/dns_session/0/0`.

You can use the following code to start a test:

```python
import domain_embedding
import dscorr
import dscorr_example

DOMAIN_VECTORS = domain_embedding.load_model('path/to/domain/embedding/model')                      # path of domain embedding model

# A simple example of reading files and choosing labeled sessions. 
# You should write your own functions to adjust your data format and experiment setting.
WORDS_N_WEIGHTS = dscorr_example.read_data(DOMAIN_VECTORS, 'path/to/dns/session/data')              # eg, sample/dns_session
LABELED_WW, UNLABELED_WW = dscorr_example.select_test_sessions(WORDS_N_WEIGHTS, 10)                 # choose labeled sessions

####### closed-world settings #######
# ds = dscorr.DSCorrClosed()
# ds.set(KNOWN_WW, DOMAIN_VECTORS)

####### open-world settings #######
ds = dscorr.DSCorrOpen()
ds.set(LABELED_WW, DOMAIN_VECTORS, theta=1)

for t in UNLABELED_WW:
    ds.test_single_session(t, num_nearest=50, prt=True)  # test sessions, print result detail.
```

See `dscorr_example.py` for examples.

See `dscorr.py` for more details of DSCorr.