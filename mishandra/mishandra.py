from __future__ import print_function, absolute_import

import sys, os, random, glob, shutil
import numpy as np

from .proto import base_pb2
from .utils.text import colored, decorated
from .utils import *

import collections
collections_abc = getattr(collections, 'abc', collections)

from cassandra.cluster import Cluster
from cassandra.query import dict_factory
from cassandra.query import SimpleStatement
from cassandra import ConsistencyLevel

class MishandraSession():
  """Mishandra entry point. Handles communication with a cluster. Contains routines for data I/O."""
  version = "0.1.0"
  def __init__(self, contact_points=None, port=9042, verbose=False):
    if contact_points is None:
      self.cluster = self.db_session = None
      print("Contact points are not set. Cluster will not be available")
    else:
      try:
        self.cluster = Cluster(contact_points, port)
        self.db_session = self.cluster.connect()
        self.db_session.row_factory = dict_factory
      except Exception as e:
        self.cluster = self.db_session = None
        print("Cannot connect to cluster")
        print(e)

    self.cfg = {
      "per_row_partition": True,
      "n_frameset_cols": 512,
      "default_partition": 0, 
      "blob_size": 2**20,
      "n_non_data_attribs": 4,
      "attributes": [
        ['partition',      'int'],
        ['id',          'bigint'],
        ['storage_mode',   'int'],
        ['sizes',         'text']
      ],
      "primary_key": ["partition", "id"]
    }
    self.attributes = self.cfg["attributes"]
    self.n_non_data_attribs=  self.cfg["n_non_data_attribs"]

    self.keyspace = None
    for i in range(self.cfg["n_frameset_cols"]):
      self.attributes.append(("p_{}".format(i), 'blob'))
    self.primary_key = ", ".join(self.cfg["primary_key"])
    self.verbose = verbose
    self.mishandra = colored.blue("Mishandra")

    print("{} session created".format(self.mishandra))
    if verbose:
      self.print_keyspaces()

  @staticmethod
  def ping_cassandra():
    session = MishandraSession()
    session.print_keyspaces(keyspace_exclude=None)

  def attrib_ph(self, n_cols):
    return "(" + ", ".join(["%s"] * n_cols) + ")"

  def attrib_names_typed(self):
    return "(" + ", ".join(["{} {}".format(name, type) for name, type in self.attributes]) + (", PRIMARY KEY({})".format(self.primary_key)) + ")"

  def attrib_names(self, n_cols):
    return "(" + ", ".join(["{}".format(name, type) for name, type in self.attributes[:n_cols]]) + ")"

  def create_insert_mesh_query(self, collection, n_cols, consistency_level=ConsistencyLevel.ONE, keyspace=None):
    if keyspace is None:
      keyspace = self.keyspace
    query = SimpleStatement(
      "INSERT INTO {}.{} {} VALUES {};".format(keyspace, collection, self.attrib_names(n_cols), self.attrib_ph(n_cols)),
      consistency_level=consistency_level
    )      
    return query

  def set_keyspace(self, name, use_simple_strategy=True, replication_factor=1):
    if use_simple_strategy:
      if type(replication_factor) is not int:
        print("Please set replication_factor as a single number")
        return
      replication_strategy = 'SimpleStrategy'
      replication = "'replication_factor' : {}".format(replication_factor)
    else:
      replication_strategy = 'NetworkTopologyStrategy'
      if type(replication_factor) is not dict or len(replication_factor) < 1:
        print("Please specity replication_factor for each datacenter in order to use NetworkTopologyStrategy")
        return
      replication = []
      for dc_name, dc_rf in replication_factor.items():
        replication.append("'{}': {}".format(dc_name, dc_rf))
        replication = ", ".join(replication)
    cmd = "CREATE KEYSPACE IF NOT EXISTS {} WITH REPLICATION = {{'class' : '{}', {}}};".format(name, replication_strategy, replication)
    self.db_session.execute(cmd)
    self.keyspace = name
    if self.verbose:
      print("Current keyspace: {}".format(decorated.bold(colored.blue(name))))
      self.print_keyspaces()

  def delete_keyspace(self, name):
    try:
      self.db_session.execute(
        "DROP KEYSPACE {};".format(name)
      )
      if name == self.keyspace:
        self.keyspace = None
      if self.verbose:
        print("Keyspace {} dropped".format(decorated.bold(colored.blue(name))))
        self.print_keyspaces()
    except Exception as e:
      print(e)

  def get_keyspace_checked(self):
    if self.keyspace is None:
      raise AttributeError("Please set a keyspace to operate with")
    return self.keyspace

  def print_keyspaces(
    self,
    show_collections=True,
    keyspace_exclude='system',
    keyspace_include=None,
    collection_exclude=None,
    collection_include=None,
    indent=False
  ):
    try:
      if indent:
        print()
      ks_rows = self.db_session.execute("SELECT * FROM system_schema.keyspaces;")
      printed = False
      print("Keyspaces:")
      for row in ks_rows:
        keyspace_name = row['keyspace_name']
        if keyspace_exclude is not None and keyspace_exclude in keyspace_name:
          continue       
        if keyspace_include is not None and not keyspace_include in keyspace_name:
          continue
        print("{} (durable_writes: {}, replication: {})".format(decorated.bold(colored.blue(keyspace_name)), row['durable_writes'], row['replication']))
        if show_collections:
          tab_rows = self.db_session.execute(
            "SELECT * FROM system_schema.tables WHERE keyspace_name = '{}';".format(keyspace_name)
          )
          for tab_row in tab_rows:
            table_name = tab_row['table_name']
            if collection_exclude is not None and collection_exclude in table_name:
              continue       
            if collection_include is not None and not collection_include in table_name:
              continue
            num_rows = self.db_session.execute("SELECT COUNT(*) FROM {}.{};".format(keyspace_name, tab_row['table_name']))
            print("   table {} (rows: {})".format(decorated.bold(colored.blue(table_name)), num_rows[0]['count']))
        if indent:
          print()
        printed = True
      if not printed:
        print("No user defined keyspaces")
    except:
      pass

  def get_table_names(self, keyspace):
    tables = self.db_session.execute(
      "SELECT table_name FROM system_schema.tables WHERE keyspace_name='{}';".format(keyspace)
    )
    return [table.table_name for table in tables]

  def create_collection(self, name, keyspace=None):
    try:
      if keyspace is None:
        keyspace = self.get_keyspace_checked()
      def create(suffix=''):
        comb_name = "{}.{}{}".format(keyspace, name, suffix)
        self.db_session.execute(
          "CREATE TABLE IF NOT EXISTS {} {};".format(comb_name, self.attrib_names_typed())
        )
        if self.verbose:
          print("Table {}.{}{}".format(decorated.bold(colored.blue(keyspace)), decorated.bold(colored.blue(name)), suffix))
          self.print_keyspaces()
      create()
    except Exception as e:
      print(e)

  def clear_collection(self, name, keyspace=None):
    try:
      if keyspace is None:
        keyspace = self.get_keyspace_checked()
      def truncate(suffix=''):
        comb_name = "{}.{}{}".format(keyspace, name, suffix)
        self.db_session.execute(
          "TRUNCATE {};".format(comb_name)
        )
        if self.verbose:
          print("Table {}.{}{} truncated".format(decorated.bold(colored.blue(keyspace)), decorated.bold(colored.blue(name)), suffix))
          self.print_keyspaces()
      truncate()
    except Exception as e:
      print(e)

  def delete_collection(self, name, keyspace=None):
    try:
      if keyspace is None:
        keyspace = self.get_keyspace_checked()
      def drop(suffix=''):
        comb_name = "{}.{}{}".format(keyspace, name, suffix)
        self.db_session.execute(
          "DROP TABLE {};".format(comb_name)
        )
        if self.verbose:
          print("Table {}.{}{} dropped".format(decorated.bold(colored.blue(keyspace)), decorated.bold(colored.blue(name)), suffix))
          self.print_keyspaces()
      drop()
    except Exception as e:
      print(e)

  def split_even(self, pack_blob):
    sizes, blobs = [], []
    blob_size = self.cfg["blob_size"]
    pack_blob = bytearray(pack_blob)
    blob_size_total = len(pack_blob)
    end = 0
    while True:
      start = end
      end = start + blob_size
      if start >= blob_size_total:
        break
      end = min(end, blob_size_total)
      sizes.append(end - start)
      blobs.append(pack_blob[start:end])
    return (sizes, blobs)

  def combine_even(self, blobs):
    pack_blob = bytearray()
    for blob in blobs:
      pack_blob += blob
    return pack_blob

  def save_pack_to_cluster(
    self,
    collection,
    id,
    pack,
    keyspace=None,
    consistency_level=ConsistencyLevel.ONE,
    as_even_blobs=True,
    verbose=False
  ):
    try:
      if keyspace is None:
        keyspace = self.get_keyspace_checked()

      pack_is_blob = not type(pack) is base_pb2.FrameSet

      fields = [
        id if self.cfg["per_row_partition"] else self.cfg["default_partition"],
        id
      ]
      if not pack_is_blob:
        pack.id = id

      sizes = []
      blobs = []
      if not as_even_blobs and not pack_is_blob:
        storage_mode = 0
        for frameset in pack.frameSets:
          blob = frameset.SerializeToString()
          if sys.version_info[0] < 3:
            blob = bytearray(blob)
          sizes.append(len(blob))
          blobs.append(blob)
      else:
        storage_mode = 1
        blob = pack if pack_is_blob else pack.SerializeToString()
        sizes, blobs = self.split_even(blob)

      total_size = sum([len(blob)//2**10 for blob in blobs])
      if verbose:
        print("Id: {}, Storage Mode: {}, Size: {}KB, Blobs: {}".format(id, storage_mode, total_size, len(blobs)))

      fields.append(storage_mode)
      fields.append(",".join([str(size) for size in sizes]))
      for blob in blobs:
        fields.append(blob)

      query = self.create_insert_mesh_query(collection, n_cols=len(blobs)+self.n_non_data_attribs, keyspace=keyspace, consistency_level=consistency_level)
      self.db_session.execute(query, fields)
      return total_size
    except Exception as e:
      print(e)
      return None

  def directory_to_cluster_collection(
    self,
    directory,
    collection,
    keyspace=None,
    clear_collection=True,
    consistency_level=ConsistencyLevel.ONE,
    as_even_blobs=True,
    verbose=False
  ):
    try:
      if keyspace is None:
        keyspace = self.get_keyspace_checked()
      if self.cluster is None:
        print("Cluster is not available")
        return None
      if collection is None or keyspace is None or len(collection) < 1 or len(keyspace) < 1:
        print("Bad collection or keyspace name")
        return None
      if not os.path.isdir(directory):
        print("Directory doesn't exist")
        return None
      
      files = glob.glob(directory + '/*.mi')
      files = list(sorted(files))
      if len(files) < 1:
        print("No Mishandra files found in {}".format(directory))
        return None

      mega_fpath = None
      for file in files:
        fname = os.path.basename(file)
        if megapack_file_name == fname:
          mega_fpath = file
      if mega_fpath is not None and len(files) > 1:
        print("Megapack and regular packs are present in {}. Skipping".format(directory))
        return

      packs, ids = [], []
      if mega_fpath is not None:
        packs = self.megapack_to_packs(directory, save_packs=False)
        for pack in packs:
          ids.append(pack.id)
      else:
        for fpath in files:
          if as_even_blobs:
              with open(fpath, 'rb') as f:
                  pack = f.read()
              ids.append(int(os.path.basename(fpath).split('.')[0]))
              packs.append(pack)

          else:
              ids.append(pack.id)
              packs.append(self.load_pack_from_file(fpath))

      if len(packs) > 0:
        self.clear_collection(collection, keyspace=keyspace)
        total_size = 0
      for i, pack in enumerate(packs):
        if pack is None:
          print("Trying to save None pack")
          continue
        size = self.save_pack_to_cluster(
            keyspace=keyspace,
            collection=collection,
            id=ids[i],
            pack=pack,
            as_even_blobs=as_even_blobs, 
            verbose=verbose
        )
        total_size += size if size is not None else 0

      print("Saved {}KB".format(total_size))
      return total_size

    except Exception as e:
      print(e)
      return None

  def cluster_collection_to_directory(
    self,
    directory,
    collection,
    keyspace=None,
    masterpack_id=None,
    as_blob=True,
    verbose=False
  ):
    try:
      if keyspace is None:
        keyspace = self.get_keyspace_checked()
      if self.cluster is None:
        print("Cluster is not available")
        return None

      ids = []
      rows = self.db_session.execute("SELECT distinct {} FROM {}.{};".format(self.cfg["primary_key"][0], keyspace, collection))
      for row in rows:
        ids.append(row["partition"])
      if verbose:
        print("{} {}: {} keys".format(keyspace, collection, len(ids)))

      ids = sorted(ids)

      if os.path.isdir(directory):
        shutil.rmtree(directory, ignore_errors=True)
      os.makedirs(directory)

      for id in ids:
        pack = self.load_pack_from_cluster(collection, keyspace, id, as_blob=as_blob)
        fpath = os.path.join(directory, id_to_fname(id, is_master=id==masterpack_id))
        self.save_pack_to_file(fpath, pack)

      if verbose:
        print("{} files saved to {}".format(len(ids), directory))
    except Exception as e:
      print(e)
      return None

  def load_pack_from_cluster(self, collection, keyspace=None, id=None, as_blob=False, verbose=False):
    try:
      if id is None:
        raise ValueError("Please specity a FrameSet id")
      if keyspace is None:
        keyspace = self.get_keyspace_checked()
      query = "SELECT * FROM {}.{} WHERE partition = {} AND id = {};".format(keyspace, collection, id, id)
      rows = self.db_session.execute(query)
      for row in rows:
        pack = base_pb2.FrameSet()
        pack.id = id
        sizes = row['sizes']
        sizes = sizes.split(",")
        blobs = []
        for i, size in enumerate(sizes):
          part_name = "p_{}".format(i)
          blob = row[part_name]
          if row['storage_mode'] == 0:
            frameset = pack.frameSets.add()
            frameset.ParseFromString(blob)
          elif row['storage_mode'] == 1:
            blobs.append(blob)
        if row['storage_mode'] == 0 and as_blob:
          blob = pack.SerializeToString()
          pack = blob
        if row['storage_mode'] == 1 and len(blobs) > 0:
          blob = self.combine_even(blobs)
          if as_blob:
            pack = blob
          else:
            pack.ParseFromString(blob)
        if verbose:
          print("pack {} loaded from {} {}".format(id, keyspace, collection))
        return pack
      return None
    except Exception as e:
      if verbose:
        print(e)
      return None

  def load_pack_range_from_cluster(self, collection, keyspace=None, id_from=0, id_to=10, verbose=False):
    try:
      if keyspace is None:
        keyspace = self.get_keyspace_checked()
      if any([id < 0 for id in [id_from, id_to]]) or id_from >=id_to:
        raise ValueError("Wrong id range")
      result = []
      for id in range(id_from, id_to):
        pack = self.load_pack_from_cluster(collection, keyspace, id, verbose=verbose)
        if pack is not None:
          result.append(pack)
      if self.verbose:
        print("{} rows loaded".format(len(result)))
      return result
    except Exception as e:
      print(e)

  def save_pack_to_file(self, file_path, pack):
    try:
      if any([v is None or type(v) is not t for v, t in list(zip([file_path], [str]))]):
        raise ValueError("Bad input")
      pack_is_blob = not type(pack) is base_pb2.FrameSet
      if not pack_is_blob:
        blob = pack.SerializeToString()
      else:
        blob = pack
      with open(file_path, 'wb') as f:
        f.write(blob)
    except Exception as e:
      print(e)

  def load_pack_from_file(self, file_path):
    try:
      with open(file_path, 'rb') as f:
        blob = f.read()
        pack = base_pb2.FrameSet()
        pack.ParseFromString(blob)
      return pack
    except Exception as e:
      print(e)
      return None

  def packs_to_megapack(self, directory, save_megapack=True, output_directory=None, remove_packs=False):
    try:
      if not os.path.isdir(directory):
        print("Directory doesn't exist")
        return None
      if save_megapack and output_directory is not None and not os.path.isdir(output_directory):
        print("Output directory doesn't exist")
        return None
      files = glob.glob(directory + '/*.mi')
      files = list(sorted(files))
      if len(files) < 1:
        print("No Mishandra files found in {}".format(directory))
        return None
      
      megapack = base_pb2.FrameSet()
      megapack.version = MishandraSession.version
      for fpath in files:
        if megapack_file_name in os.path.basename(fpath):
          continue
        pack = self.load_pack_from_file(fpath)
        frameset = megapack.frameSets.add()
        frameset.CopyFrom(pack)
        frameset.version = MishandraSession.version
        frameset.is_master = fpath.endswith(masterpack_file_ext) or pack.is_master

      if save_megapack:
        mega_fpath = os.path.join(directory if output_directory is None else output_directory, megapack_file_name) 
        self.save_pack_to_file(mega_fpath, megapack)

      if remove_packs:
        for fpath in files:
          os.remove(fpath)

      return megapack

    except Exception as e:
      print(e)
      return None

  def megapack_to_packs(self, directory, save_packs=True, output_directory=None, remove_megapack=False):
    try:
      if not os.path.isdir(directory):
        print("Directory doesn't exist")
        return None
      mega_fpath = os.path.join(directory, megapack_file_name)
      if not os.path.isfile(mega_fpath):
        print("Megapack doesn't exist")
        return None
      if save_packs and output_directory is not None and not os.path.isdir(output_directory):
        print("Output directory doesn't exist")
        return None

      megapack = self.load_pack_from_file(mega_fpath)

      packs = []
      for i, frameset in enumerate(megapack.frameSets):
        frameset.version = MishandraSession.version
        packs.append(frameset)
        if save_packs:
          id = frameset.id
          fname = id_to_fname(id, is_master=frameset.is_master)
          fpath = os.path.join(directory if output_directory is None else output_directory, fname) 
          self.save_pack_to_file(fpath, frameset)

      if remove_megapack:
        os.remove(mega_fpath)

      return packs

    except Exception as e:
      print(e)
      return None
