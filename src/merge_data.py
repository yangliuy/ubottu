import argparse
import cPickle
import gzip
import numpy as np
import random
import sys
from collections import Counter
from twokenize import tokenize
np.random.seed(42)

parser = argparse.ArgumentParser()
parser.add_argument('--suffix', type=str, default='', help='Suffix')
parser.add_argument('--input_dir', type=str, default='../data', help='Input directory')
parser.add_argument('--output_dir', type=str, default='.', help='Output directory')
args = parser.parse_args()

TRAIN_FILE = '%s/trainset%s.csv.pkl' % (args.input_dir, args.suffix)

VAL_FILE = '%s/valset.csv.pkl' % args.input_dir
TEST_FILE = '%s/testset.csv.pkl' % args.input_dir

W2V_FILE = '../embeddings/word2vec/GoogleNews-vectors-negative300.bin'
GLOVE_FILE = '../embeddings/glove/glove.840B.300d.txt'

UNK_TOKEN='**unknown**'
BATCH_SIZE = 256

def uniform_sample(a, b, k=0):
    if k == 0:
        return random.uniform(a, b)
    ret = np.zeros((k,))
    for x in xrange(k):
        ret[x] = random.uniform(a, b)
    return ret

def get_W(word_vecs, k):
    """
    Get word matrix. W[i] is the vector for word indexed by i
    """
    vocab_size = len(word_vecs)
    word_idx_map = dict()
    W = np.zeros(shape=(vocab_size+1, k))            
    W[0] = np.zeros(k)
    i = 1
    for word in word_vecs:
        W[i] = word_vecs[word]
        word_idx_map[word] = i
        i += 1
    return W, word_idx_map

def load_bin_vec(fname, vocab):
    """
    Loads 300x1 word vecs from Google (Mikolov) word2vec
    """
    word_vecs = {}
    with open(fname, "rb") as f:
        header = f.readline()
        vocab_size, layer1_size = map(int, header.split())
        binary_len = np.dtype('float32').itemsize * layer1_size
        for line in xrange(vocab_size):
            word = []
            while True:
                ch = f.read(1)
                if ch == ' ':
                    word = ''.join(word).lower()
                    break
                if ch != '\n':
                    word.append(ch)   
            if word in vocab:
               word_vecs[word] = np.fromstring(f.read(binary_len), dtype='float32')  
            else:
                f.read(binary_len)
    return word_vecs

def load_glove_vec(fname, vocab):
    """
    Loads word vecs from gloVe
    """
    word_vecs = {}
    with open(fname, "rb") as f:
        for i,line in enumerate(f):
            L = line.split()
            word = L[0].lower()
            if word in vocab:
                word_vecs[word] = np.array(L[1:], dtype='float32')
    return word_vecs

def add_unknown_words(word_vecs, vocab, min_df=1, k=300, unk_token='**unknown**'):
    """
    For words that occur in at least min_df documents, create a separate word vector.    
    0.25 is chosen so the unknown vectors have (approximately) same variance as pre-trained ones
    """
    for word in vocab:
        if word not in word_vecs and vocab[word] >= min_df:
            word_vecs[word] = uniform_sample(-0.25,0.25,k)  
    word_vecs[unk_token] = uniform_sample(-0.25,0.25,k)

def get_idx_from_sent(sent, word_idx_map, k):
    """
    Transforms sentence into a list of indices. Pad with zeroes.
    """
    x = []
    words = tokenize(sent)
    for word in words:
        if word in word_idx_map:
            x.append(word_idx_map[word])
        else:
            x.append(word_idx_map[UNK_TOKEN])
    return x

def make_idx_data(dataset, word_idx_map, k=300):
    """
    Transforms sentences into a 2-d matrix.
    """
    for i in xrange(len(dataset['y'])):
        dataset['c'][i] = get_idx_from_sent(dataset['c'][i], word_idx_map, k)
        dataset['r'][i] = get_idx_from_sent(dataset['r'][i], word_idx_map, k)

def pad_to_batch_size(X, batch_size):
    n_seqs = len(X)
    n_batches_out = np.ceil(float(n_seqs) / batch_size)
    n_seqs_out = batch_size * n_batches_out

    to_pad = n_seqs % batch_size
    if to_pad > 0:
        X += X[:batch_size-to_pad]
    return X

def main():
    train_data, train_vocab = cPickle.load(open(TRAIN_FILE))
    val_data, val_vocab = cPickle.load(open(VAL_FILE))
    test_data, test_vocab = cPickle.load(open(TEST_FILE))

    vocab = train_vocab + val_vocab + test_vocab
    del train_vocab, val_vocab, test_vocab

    print "data loaded!"
    print "num train: ", len(train_data['y'])
    print "num val: ", len(val_data['y'])
    print "num test: ", len(test_data['y'])
    print "vocab size: ", len(vocab)

    print "loading embeddings..."
    #embeddings = load_bin_vec(W2V_FILE, vocab)
    embeddings = load_glove_vec(GLOVE_FILE, vocab)

    print "embeddings loaded!"
    print "num words with embeddings: ", len(embeddings)

    add_unknown_words(embeddings, vocab, min_df=2)
    W, word_idx_map = get_W(embeddings, k=300)
    print "W: ", W.shape

    for key in ['c', 'r', 'y']:
        for dataset in [train_data, val_data]:
            dataset[key] = pad_to_batch_size(dataset[key], BATCH_SIZE)

    make_idx_data(train_data, word_idx_map)
    make_idx_data(val_data, word_idx_map)
    make_idx_data(test_data, word_idx_map)

    for key in ['c', 'r', 'y']:
        print key
        for dataset in [train_data, val_data, test_data]:
            print len(dataset[key])

    cPickle.dump([train_data, val_data, test_data], open('%s/dataset%s.pkl' % (args.output_dir, args.suffix), 'wb'), protocol=-1)
    del train_data, val_data, test_data

    cPickle.dump([W, word_idx_map], open("%s/W%s.pkl" % (args.output_dir, args.suffix), "wb"), protocol=-1)
    del W

    rand_vecs = {}
    add_unknown_words(rand_vecs, vocab, min_df=2)
    W2, _ = get_W(rand_vecs, k=300)
    print "W2: ", W2.shape
    cPickle.dump([W2, word_idx_map], open("%s/W2%s.pkl" % (args.output_dir, args.suffix), "wb"), protocol=-1)
    del W2

    cPickle.dump(vocab, open('%s/vocab%s.pkl' % (args.output_dir, args.suffix), 'wb'), protocol=-1)
    del vocab

    print "dataset created!"

if __name__ == '__main__':
  main()

