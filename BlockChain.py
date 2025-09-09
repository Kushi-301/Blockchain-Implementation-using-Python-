

from __future__ import annotations
import hashlib            #used to import SHA-256 
import json               # JavaScript Object Notation used for block , transactions --> as objects/strings 
import time               #timestamps 
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()  #Converts string to bytes and implements hash function

def current_timestamp() -> float:
    return time.time()

@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: int

    def to_dict(self) -> Dict[str, Any]:             #creating key value pair for the transaction 
        return {"sender": self.sender, "recipient": self.recipient, "amount": self.amount}

    def id(self) -> str:
        return sha256(json.dumps(self.to_dict(), sort_keys=True)) #JSON to ids
        # returns a unique TRANSACTION ID for the transaction in sorted order 

@dataclass
class Block:      #creates the block of the blockchain 
    index: int
    timestamp: float
    transactions: List[Transaction]
    previous_hash: str
    nonce: int = 0      # number miners change until the block hash satisfies the difficulty target (3 here)
    difficulty: int = 3 #no of leading zeroes the hash must have
    hash: Optional[str] = None #hash of this block 

    def compute_hash(self) -> str:
        block_dict = {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
        }
        return sha256(json.dumps(block_dict, sort_keys=True)) #Converts the dictionary into a JSON string

class Blockchain:      #the ledger 
    def __init__(self, *, difficulty: int = 3, block_reward: int = 50) -> None:    #constructor type in python 
        self.difficulty = difficulty
        self.block_reward = block_reward    #how many coins miners get for mining a block
        self.chain: List[Block] = [] #pending transactions not yet mined
        self.current_transactions: List[Transaction] = []
        self.addresses: Dict[str, int] = {}
        self.create_genesis_block()  #the very first block 

    def create_genesis_block(self) -> None:
        faucet = "faucet"
        faucet_allocation = 10_000
        self.addresses[faucet] = faucet_allocation
        genesis_tx = Transaction(sender="coinbase", recipient=faucet, amount=faucet_allocation) #Coinbase to faucet transition 
        block = Block(index=0, timestamp=current_timestamp(), transactions=[genesis_tx], previous_hash="0" * 64, difficulty=self.difficulty)
        block.hash = block.compute_hash()
        self.chain.append(block)

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def get_balance(self, address: str) -> int:
        balances: Dict[str, int] = {}
        for block in self.chain:
            for tx in block.transactions:
                if tx.sender != "coinbase":
                    balances[tx.sender] = balances.get(tx.sender, 0) - tx.amount
                balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
        for tx in self.current_transactions:
            if tx.sender != "coinbase":
                balances[tx.sender] = balances.get(tx.sender, 0) - tx.amount
            balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
        return balances.get(address, 0)

    def add_transaction(self, sender: str, recipient: str, amount: int) -> str:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if sender == "coinbase":
            raise ValueError("'coinbase' is reserved for miner rewards")
        if self.get_balance(sender) < amount:
            raise ValueError("Insufficient balance for transaction")
        tx = Transaction(sender=sender, recipient=recipient, amount=amount)
        self.current_transactions.append(tx)
        return tx.id()

    def mine_block(self, miner_address: str) -> Block:
        coinbase_tx = Transaction(sender="coinbase", recipient=miner_address, amount=self.block_reward)
        txs = [coinbase_tx] + self.current_transactions
        block = Block(
            index=self.last_block.index + 1,
            timestamp=current_timestamp(),
            transactions=txs,
            previous_hash=self.last_block.hash or "0" * 64,
            difficulty=self.difficulty,
        )
        target_prefix = "0" * self.difficulty
        while True:
            h = block.compute_hash()
            if h.startswith(target_prefix):
                block.hash = h
                break
            block.nonce += 1
        self.chain.append(block)
        self.current_transactions = []
        return block

    def valid_block(self, block: Block, prev_block: Optional[Block]) -> bool:
        if prev_block:
            if block.previous_hash != (prev_block.hash or prev_block.compute_hash()):
                return False
            if block.index != prev_block.index + 1:
                return False
        else:
            if block.index != 0:
                return False
        if not block.hash or not block.hash.startswith("0" * block.difficulty):
            if block.index != 0:
                return False
        balances: Dict[str, int] = {}
        for b in self.chain[:block.index]:
            for tx in b.transactions:
                if tx.sender != "coinbase":
                    balances[tx.sender] = balances.get(tx.sender, 0) - tx.amount
                balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
        for tx in block.transactions:
            if tx.sender != "coinbase":
                if balances.get(tx.sender, 0) < tx.amount:
                    return False
                balances[tx.sender] = balances.get(tx.sender, 0) - tx.amount
            balances[tx.recipient] = balances.get(tx.recipient, 0) + tx.amount
        return True

    def valid_chain(self, chain: List[Block]) -> bool:
        if not chain:
            return False
        for i, block in enumerate(chain):
            prev = chain[i - 1] if i > 0 else None
            saved_chain = self.chain
            try:
                self.chain = chain[:i]
                if not self.valid_block(block, prev):
                    return False
            finally:
                self.chain = saved_chain
        return True

    def replace_chain(self, new_chain: List[Block]) -> bool:
        if len(new_chain) > len(self.chain) and self.valid_chain(new_chain):
            self.chain = [
                Block(
                    index=b.index,
                    timestamp=b.timestamp,
                    transactions=[Transaction(**tx.to_dict()) for tx in b.transactions],
                    previous_hash=b.previous_hash,
                    nonce=b.nonce,
                    difficulty=b.difficulty,
                    hash=b.hash,
                )
                for b in new_chain
            ]
            self.current_transactions = []
            return True
        return False

class Node:
    def __init__(self, name: str, *, difficulty: int = 3, block_reward: int = 50):
        self.name = name
        self.blockchain = Blockchain(difficulty=difficulty, block_reward=block_reward)
        self.peers: List[Node] = []

    def connect(self, other: "Node") -> None:
        if other is self:
            return
        if other not in self.peers:
            self.peers.append(other)
        if self not in other.peers:
            other.peers.append(self)

    def broadcast_block(self, block: Block) -> None:
        for p in self.peers:
            if p.blockchain.valid_block(block, p.blockchain.last_block):
                p.blockchain.chain.append(block)
                p.blockchain.current_transactions = []

    def new_tx(self, sender: str, recipient: str, amount: int) -> str:
        return self.blockchain.add_transaction(sender, recipient, amount)

    def mine(self) -> Block:
        block = self.blockchain.mine_block(miner_address=self.name)
        self.broadcast_block(block)
        return block

    def resolve_conflicts(self) -> bool:
        candidate = self.blockchain.chain
        for p in self.peers:
            if len(p.blockchain.chain) > len(candidate) and self.blockchain.valid_chain(p.blockchain.chain):
                candidate = p.blockchain.chain
        return self.blockchain.replace_chain(candidate)

    def balance(self, address: str) -> int:
        return self.blockchain.get_balance(address)

if __name__ == "__main__":
    random.seed(7)

    p1 = Node("P1", difficulty=3, block_reward=50)
    p2 = Node("P2", difficulty=3, block_reward=50)
    p3 = Node("P3", difficulty=3, block_reward=50)

    p1.connect(p2)
    p2.connect(p3)
    p3.connect(p1)

    faucet = "faucet"
    p1.blockchain.add_transaction(faucet, "P1", 200)
    p1.blockchain.add_transaction(faucet, "P2", 200)
    p1.blockchain.add_transaction(faucet, "P3", 200)

    print("\n=== P1 mines funding block ===")
    block1 = p1.mine()
    print(f"P1 mined block #{block1.index} with hash {block1.hash[:16]}...")

    print("Balances after funding:")
    for n in (p1, p2, p3):
        print(f"  On {n.name}'s view -> P1: {n.balance('P1')}, P2: {n.balance('P2')}, P3: {n.balance('P3')}")

    p2.new_tx("P2", "P3", 30)
    p3.new_tx("P3", "P1", 25)

    print("\n=== P2 and P3 race to mine (possible fork) ===")
    b2 = p2.mine()
    c2 = p3.mine()
    print(f"P2 mined block #{b2.index} -> {b2.hash[:16]}...; P3 mined block #{c2.index} -> {c2.hash[:16]}...")

    print("\n=== Consensus: resolve conflicts (longest valid chain wins) ===")
    for n in (p1, p2, p3):
        changed = n.resolve_conflicts()
        print(f"{n.name} {'adopted a longer chain' if changed else 'kept its chain'}; height={len(n.blockchain.chain)-1}")

    print("\n=== P1 mines another block to extend the winning chain ===")
    a3 = p1.mine()
    print(f"P1 mined block #{a3.index} -> {a3.hash[:16]}...")

    for n in (p1, p2, p3):
        n.resolve_conflicts()

    print("\n=== Final Balances on each node's view ===")
    for n in (p1, p2, p3):
        print(f"[{n.name}] P1: {n.balance('P1')} | P2: {n.balance('P2')} | P3: {n.balance('P3')} | Miner({n.name}): {n.balance(n.name)}")

    print("\n=== Final chain (as seen by P1) ===")
    for b in p1.blockchain.chain:
        print(f"Block #{b.index} | prev={b.previous_hash[:8]} | hash={b.hash[:8]} | txs={len(b.transactions)} | nonce={b.nonce}")
