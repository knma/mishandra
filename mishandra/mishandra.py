import sys, os, random
import numpy as np
import pandas as pd
from types import SimpleNamespace
from collections.abc import Iterable

from .proto import base_pb2
from .utils.text import colored, decorated

from cassandra.cluster import Cluster
from cassandra.query import named_tuple_factory
from cassandra.query import SimpleStatement
from cassandra import ConsistencyLevel

module = sys.modules[__name__]
module.session3d = None


class MishandraSession():
  """Mishandra entry point. Handles communication with cassandra cluster. Contains routines for data I/O."""
  def __init__(self, contact_points=('127.0.0.1',), port=9042, verbose=True):
    self.cluster = Cluster(contact_points, port)
    self.session = self.cluster.connect()
    self.partition = 0
    self.keyspace = None
    self.attributes = [
      ('partition',     'int'),
      ('frame',         'bigint'),
      ('data',          'blob'),
    ]
    self.primary_key = "(partition, frame)"
    self.attrib_names_list = list(zip(*self.attributes))[0]
    self.attrib_ph = "(" + ", ".join(["%s"] * len(self.attributes)) + ")"
    self.verbose = verbose
    module.session3d = self
    misha_colors = list(vars(colored).keys())[1:len(vars(colored))-1]
    self.mishandra = ""
    for l in "Mishandra":
      self.mishandra += f"{decorated.bold(vars(colored)[misha_colors[np.random.randint(len(misha_colors))]](l))}"
    # self.mishandra = decorated.bold(self.mishandra)

    if verbose:
      print(f"{self.mishandra} session created")

  def attrib_names(self, primary_key=None, no_type=True):
    return "(" + ", ".join([f"{name} {'' if no_type else type}" for name, type in self.attributes]) + \
            (f", PRIMARY KEY{primary_key}" if primary_key else "") + ")"

  def create_insert_mesh_query(self, collection, consistency_level=ConsistencyLevel.ONE):
    query = SimpleStatement(
      f"INSERT INTO {self.keyspace}.{collection} {self.attrib_names()} VALUES {self.attrib_ph};",
      consistency_level=consistency_level
    )      
    return query

  def set_keyspace(self, name, replication_strategy='SimpleStrategy', replication_factor=3):
    self.session.execute(
      f"CREATE KEYSPACE IF NOT EXISTS {name} WITH REPLICATION = {{'class' : '{replication_strategy}', 'replication_factor' : '{replication_factor}'}};"
    )
    self.keyspace = name
    if self.verbose:
      print(f"Current keyspace: {decorated.bold(colored.blue(name))}")
      self.print_keyspaces()

  def delete_keyspace(self, name):
    try:
      self.session.execute(
        f"DROP KEYSPACE {name};"
      )
      if name == self.keyspace:
        self.keyspace = None
      if self.verbose:
        print(f"Keyspace {decorated.bold(colored.blue(name))} dropped")
        self.print_keyspaces()
    except Exception as e:
      print(e)

  def check_keyspace_is_set(self):
    if self.keyspace is None:
      raise AttributeError(f"Please set a keyspace to operate with")

  def print_keyspaces(self, tables=True, exclude_str='system', indent=True):
    try:
      if indent:
        print()
      ks_rows = self.session.execute(f"SELECT * FROM system_schema.keyspaces;")
      ks_rows = pd.DataFrame(ks_rows)
      printed = False
      print("Keyspaces:")
      for index, ks_row in ks_rows.iterrows():
        if exclude_str is not None and exclude_str in ks_row['keyspace_name']:
          continue
        print(f"{decorated.bold(colored.blue(ks_row['keyspace_name']))} (durable_writes: {ks_row['durable_writes']}, replication: {ks_row['replication']})")
        if tables:
          tab_rows = self.session.execute(
            f"SELECT * FROM system_schema.tables WHERE keyspace_name = '{ks_row['keyspace_name']}';"
          )
          for tab_row in tab_rows:
            num_rows = self.session.execute(f"SELECT COUNT(*) FROM {ks_row['keyspace_name']}.{tab_row.table_name};")
            print(f"   table {decorated.bold(colored.blue(tab_row.table_name))} (rows: {num_rows[0].count})")
        if indent:
          print()
        printed = True

      if not printed:
        print(f"No user defined keyspaces")

    except:
      pass

  def get_table_names(self, keyspace):
    tables = self.session.execute(
      f"SELECT table_name FROM system_schema.tables WHERE keyspace_name='{keyspace}';"
    )
    return [table.table_name for table in tables]

  def create_collection(self, name):
    try:
      self.check_keyspace_is_set()
      def create(suffix=''):
        comb_name = f"{self.keyspace}.{name}{suffix}"
        self.session.execute(
          f"CREATE TABLE IF NOT EXISTS {comb_name} {self.attrib_names(primary_key=self.primary_key, no_type=False)} WITH COMPACT STORAGE;"
        )
        if self.verbose:
          print(f"Table {decorated.bold(colored.blue(self.keyspace))}.{decorated.bold(colored.blue(name))}{suffix}")
          self.print_keyspaces()
      create()
    except Exception as e:
      print(e)

  def clear_collection(self, name):
    try:
      self.check_keyspace_is_set()
      def truncate(suffix=''):
        comb_name = f"{self.keyspace}.{name}{suffix}"
        self.session.execute(
          f"TRUNCATE {comb_name};"
        )
        if self.verbose:
          print(f"Table {decorated.bold(colored.blue(self.keyspace))}.{decorated.bold(colored.blue(name))}{suffix} truncated")
          self.print_keyspaces()
      truncate()
    except Exception as e:
      print(e)

  def delete_collection(self, name):
    try:
      self.check_keyspace_is_set()
      def drop(suffix=''):
        comb_name = f"{self.keyspace}.{name}{suffix}"
        self.session.execute(
          f"DROP TABLE {comb_name};"
        )
        if self.verbose:
          print(f"Table {decorated.bold(colored.blue(self.keyspace))}.{decorated.bold(colored.blue(name))}{suffix} dropped")
          self.print_keyspaces()
      drop()
    except Exception as e:
      print(e)

  def save(self, collection, proto, frame, consistency_level=ConsistencyLevel.ONE, name=None, description=None):
    try:
      if any([v is None or type(v) is not t for v, t in list(zip([collection, frame, proto], [str, int, base_pb2.Row]))]):
        raise ValueError("Bad input")
      self.check_keyspace_is_set()
      query = self.create_insert_mesh_query(collection, consistency_level=consistency_level)
      if name is not None:
        proto.name = name
      if description is not None:
        proto.description = description
      blob = proto.SerializeToString()
      self.session.execute(query, (self.partition, frame, blob))
    except Exception as e:
      print(e)

  def save_to_file(self, file_path, proto):
    try:
      if any([v is None or type(v) is not t for v, t in list(zip([file_path, proto], [str, base_pb2.Row]))]):
        raise ValueError("Bad input")
      self.check_keyspace_is_set()
      blob = proto.SerializeToString()
      with open(file_path, 'wb') as f:
        f.write(blob)
    except Exception as e:
      print(e)

  def load(self, collection, frame_from=0, frame_to=1000):
    try:
      rows = self.session.execute(
        f"SELECT * FROM {self.keyspace}.{collection} WHERE partition = {self.partition} AND frame >= {frame_from} AND frame < {frame_to};"
      )
      result = []
      for row in rows:
        proto = base_pb2.Row()
        proto.ParseFromString(row.data)
        result.append(proto)
      if self.verbose:
        print(f"{len(result)} rows loaded")
      return result
    except Exception as e:
      print(e)

  def load_from_file(self, file_path):
    try:
      if any([v is None or type(v) is not t for v, t in list(zip([file_path], [str]))]):
        raise ValueError("Bad input")
      with open(file_path, 'rb') as f:
        blob = f.read()
        proto = base_pb2.Row()
        proto.ParseFromString(blob)
      return proto
    except Exception as e:
      print(e)

  @staticmethod
  def make_proto(proto=None, frame=None, name=None, description=None):
    row = base_pb2.Row()
    if proto is not None:
      row.CopyFrom(proto)
    if frame is not None:
      row.frame = frame
    if name is not None:
      row.name = name
    if description is not None:
      row.description = description
    return row

  @staticmethod
  def ping_cassandra():
    session = MishandraSession()
    session.print_keyspaces(exclude_str=None)
