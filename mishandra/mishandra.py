import sys, os
import numpy as np
import pandas as pd
from types import SimpleNamespace
from collections.abc import Iterable

from .proto import base_pb2

from cassandra.cluster import Cluster
from cassandra.protocol import NumpyProtocolHandler
from cassandra.query import named_tuple_factory
from cassandra.query import SimpleStatement
from cassandra import ConsistencyLevel


module = sys.modules[__name__]
module.session3d = None


class MishandraSession():
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
      print(f"Current keyspace: {name}")


  def delete_keyspace(self, name):
    try:
      self.session.execute(
        f"DROP KEYSPACE {name};"
      )
    except Exception as e:
      print(e)
    if self.verbose:
      print(f"Keyspace {name} dropped")


  def check_keyspace_is_set(self):
    if self.keyspace is None:
      raise Exception(f"Please set a keyspace to operate with")


  def print_keyspaces(self, tables=True, exclude_str='system'):
    try:
      ks_rows = self.session.execute(f"SELECT * FROM system_schema.keyspaces;")
      ks_rows = pd.DataFrame(ks_rows)
      for index, ks_row in ks_rows.iterrows():
        if exclude_str is not None and exclude_str in ks_row['keyspace_name']:
          continue
        print(f"Keyspace: {ks_row['keyspace_name']}, durable_writes: {ks_row['durable_writes']}, replication: {ks_row['replication']}")
        if tables:
          tab_rows = self.session.execute(
            f"SELECT * FROM system_schema.tables WHERE keyspace_name = '{ks_row['keyspace_name']}';"
          )
          for tab_row in tab_rows:
            num_rows = self.session.execute(f"SELECT COUNT(*) FROM {ks_row['keyspace_name']}.{tab_row.table_name};")
            print(f"  Table: {tab_row.table_name}, rows: {num_rows[0].count}")
        print()
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
      def create(name_suffix=''):
        comb_name = f"{self.keyspace}.{name}{name_suffix}"
        self.session.execute(
          f"CREATE TABLE IF NOT EXISTS {comb_name} {self.attrib_names(primary_key=self.primary_key, no_type=False)};"
        )
        if self.verbose:
          print(f"Table {comb_name} created")
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
          print(f"Table {comb_name} truncated")
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
          print(f"Table {comb_name} dropped")
      drop()
    except Exception as e:
      print(e)


  def save(self, collection, frame, proto, consistency_level=ConsistencyLevel.ONE, name=None, description=None):
    try:
      if any([v is None or type(v) is not t for v, t in list(zip([collection, frame, proto], [str, int, base_pb2.Row]))]):
        raise Exception("Bad input")
      self.check_keyspace_is_set()
      query = self.create_insert_mesh_query(collection, consistency_level=consistency_level)
      proto.frame = frame
      if name is not None:
        proto.name = name
      if description is not None:
        proto.description = description
      self.session.execute(query, (self.partition, frame, proto.SerializeToString()))
    except Exception as e:
      print(e)


  def load(self, collection, frame_from=0, frame_to=1000):
    try:
      self.check_keyspace_is_set()
      rows = self.session.execute(
        f"SELECT * FROM {self.keyspace}.{collection} WHERE partition = {self.partition} AND frame >= {frame_from} AND frame < {frame_to};"
      )
      result = []
      for row in rows:
        proto = base_pb2.Row()
        proto.ParseFromString(row.data)
        result.append(proto)
      return result

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