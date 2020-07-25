from types import SimpleNamespace as SN

byte_field_descriptions = SN(
  PointSet = SN(
    P =       SN(shape=(-1,3), dtype=np.float32),
    N =       SN(shape=(-1,3), dtype=np.float32),
    v =       SN(shape=(-1,3), dtype=np.float32),
    scale =   SN(shape=(-1,3), dtype=np.float32),
    Cd =      SN(shape=(-1,3), dtype=np.float32),
    Alpha =   SN(shape=(-1,1), dtype=np.float32),
    Cs =      SN(shape=(-1,3), dtype=np.float32),
    Cr =      SN(shape=(-1,3), dtype=np.float32),
    Ct =      SN(shape=(-1,3), dtype=np.float32),
    Ce =      SN(shape=(-1,3), dtype=np.float32),
    rough =   SN(shape=(-1,3), dtype=np.float32),
    fresnel = SN(shape=(-1,3), dtype=np.float32),
    shadow =  SN(shape=(-1,3), dtype=np.float32),
    group =   SN(shape=(-1,3), dtype=np.float32),
  ),
)

bfd.PointSet = SN()


syntax = "proto3";

message PointSet {
  string name = 1;
  bytes P = 2;                        // position (n,3,)
  bytes N = 3;                        // normal (n,3,)
  bytes v = 4;                        // velocity (n,3,)
  bytes scale = 5;                    // scale (n,3,)
  bytes Cd = 6;                       // diffuse color (n,3,)
  bytes Alpha = 7;                    // alpha (n,)
  bytes Cs = 8;                       // specular color (n,3,)
  bytes Cr = 9;                       // reflect color (n,3,)
  bytes Ct = 10;                      // transmit color (n,3,)
  bytes Ce = 11;                      // emission color (n,3,)
  bytes rough = 12;                   // roughness (n,)
  bytes fresnel = 13;                 // fresnel coefficient (n,)
  bytes shadow = 14;                  // shadow intensity (n,)
  bytes group = 15;                   // point group (n,)
}

message Transform {
  string name = 1;
  bytes T = 2;                        // translation (3,)
  bytes Q = 3;                        // quaternion (4,)
}

message Camera {
  string name = 1;
  Transform extrinsic = 2;            // extrinsic parameters
  bytes intrinsic = 3;                // camera matrix (3,3)
  bytes distCoeffs = 4;               // distortion coefficients {8,}
}

message Image {
  string name = 1;
  string format = 2;                  // jpg / png
  uint32 width = 3;
  uint32 height = 4;
  uint32 channels = 5;
  uint32 png_comression = 6;          // 0..9
  uint32 jpeg_quality = 7;            // 0..100
  bytes data = 8;                     // encoded image data
}

message ImageRaw {
  string name = 1;
  uint32 width = 2;
  uint32 height = 3;
  uint32 channels = 4;
  uint32 bytes_per_channel = 5;
  bytes data = 6;
}

message Mesh {
  string name = 1;
  PointSet pointSet = 2;
  bytes faces = 3;                    // point indices (m,3,)
}

message Object {
  string name = 1;
  Transform transform = 2;
  PointSet pointSet = 3;
  Mesh mesh = 4;
  Camera camera = 5;
  repeated Image image = 6;
  repeated ImageRaw imageRaw = 7;
}

message Scene {
  string name = 1;
  repeated Object objects = 2;
}

message Row {
  uint32 id = 1;
  string name = 2;
  repeated Scene scenes = 3;          // collection of Scenes (N,)
}