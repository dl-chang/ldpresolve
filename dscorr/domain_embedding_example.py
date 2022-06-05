import domain_embedding

# example: train embedding model
def train():
    domain_embedding.word2vec_train(
        dns_path='path/to/dns/logs',  # eg, sample/dns_log
        model_path='path/to/domain/embedding/model',
        dns_log_params={
            'de_duplicate': True,
            'max_interval': 300,
            'max_len': 7200
        },
        w2v_params={
            'sg': 1,
            'sample': 1e-5,
            'negative': 5,
            'vector_size': 200,
            'window': 10,
            'min_count':5,
            'workers': 16,
        })

# example: get most similar domains of a given domain
def find_similar():
    model = domain_embedding.load_model('path/to/domain/embedding/model')
    d = 'www.example.com'
    print(f'most similar domain of {d}:')
    for sim_d, sim_v in model.most_similar(d):
        print(f'{sim_v:.3f},  {sim_d}')

if __name__ == '__main__':
    train()
    find_similar()
