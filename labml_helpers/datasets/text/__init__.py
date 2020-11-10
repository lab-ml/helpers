from pathlib import PurePath, Path
from typing import List, Callable, Dict, Optional

import torch
from torch.utils.data import IterableDataset

from labml import monit


class TextDataset:
    itos: List[str]
    stoi: Dict[str, int]
    n_tokens: int
    train: str
    valid: str
    standard_tokens: List[str] = []

    @staticmethod
    def load(path: PurePath):
        with open(str(path), 'r') as f:
            return f.read()

    def __init__(self, path: PurePath, tokenizer: Callable, train: str, valid: str, test: str):
        self.test = test
        self.valid = valid
        self.train = train
        self.tokenizer = tokenizer
        self.path = path

        self.n_tokens = len(self.standard_tokens)
        self.stoi = {t: i for i, t in enumerate(self.standard_tokens)}

        with monit.section("Tokenize"):
            tokens = self.tokenizer(self.train) + self.tokenizer(self.valid)
            tokens = sorted(list(set(tokens)))

        for t in monit.iterate("Build vocabulary", tokens):
            self.stoi[t] = self.n_tokens
            self.n_tokens += 1

        self.itos = [''] * self.n_tokens
        for t, n in self.stoi.items():
            self.itos[n] = t

    def text_to_i(self, text: str) -> torch.Tensor:
        tokens = self.tokenizer(text)
        return torch.tensor([self.stoi[s] for s in tokens], dtype=torch.long)

    def __repr__(self):
        return f'{len(self.train) / 1_000_000 :,.2f}M, {len(self.valid) / 1_000_000 :,.2f}M - {str(self.path)}'


class SequentialDataLoader(IterableDataset):
    def __init__(self, *, text: str, dataset: TextDataset,
                 batch_size: int, seq_len: int):
        self.seq_len = seq_len
        data = dataset.text_to_i(text)
        n_batch = data.shape[0] // batch_size
        data = data.narrow(0, 0, n_batch * batch_size)
        data = data.view(batch_size, -1).t().contiguous()
        self.data = data

    def __len__(self):
        return self.data.shape[0] // self.seq_len

    def __iter__(self):
        self.idx = 0
        return self

    def __next__(self):
        if self.idx >= self.data.shape[0] - 1:
            raise StopIteration()

        seq_len = min(self.seq_len, self.data.shape[0] - 1 - self.idx)
        i = self.idx + seq_len
        data = self.data[self.idx: i]
        target = self.data[self.idx + 1: i + 1]
        self.idx = i
        return data, target

    def __getitem__(self, idx):
        seq_len = min(self.seq_len, self.data.shape[0] - 1 - idx)
        i = idx + seq_len
        data = self.data[idx: i]
        target = self.data[idx + 1: i + 1]
        return data, target


class TextFileDataset(TextDataset):
    standard_tokens = []

    @staticmethod
    def download(url: str, path: Path):
        import urllib.request
        if not path.parent.exists():
            path.parent.mkdir(parents=True)
        with monit.section("Download") as s:
            def reporthook(count, block_size, total_size):
                s.progress(count * block_size / total_size)

            urllib.request.urlretrieve(url, path, reporthook=reporthook)

    def __init__(self, path: PurePath, tokenizer: Callable, *,
                 url: Optional[str] = None,
                 filter_subset: Optional[int] = None):
        path = Path(path)
        if not path.exists():
            if not url:
                raise FileNotFoundError(str(path))
            else:
                self.download(url, path)

        with monit.section("Load data"):
            text = self.load(path)
            if filter_subset:
                text = text[:filter_subset]
            split = int(len(text) * .9)
            train = text[:split]
            valid = text[split:]

        super().__init__(path, tokenizer, train, valid, '')


def _test_tiny_shakespeare():
    from labml import lab
    _ = TextFileDataset(lab.get_data_path() / 'tiny_shakespeare.txt', lambda x: list(x),
                        url='https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt')


if __name__ == '__main__':
    _test_tiny_shakespeare()