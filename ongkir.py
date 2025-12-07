import React, { useState, useMemo } from 'react';
import { Upload, Search, MapPin, Truck, DollarSign, Package, ChevronRight, AlertCircle, FileText } from 'lucide-react';

const Card = ({ children, className = "" }) => (
  <div className={`bg-white rounded-xl shadow-sm border border-slate-200 ${className}`}>
    {children}
  </div>
);

const Badge = ({ children, color = "blue" }) => {
  const colors = {
    blue: "bg-blue-100 text-blue-700",
    green: "bg-emerald-100 text-emerald-700",
    amber: "bg-amber-100 text-amber-700",
    slate: "bg-slate-100 text-slate-700",
    red: "bg-rose-100 text-rose-700",
  };
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[color] || colors.blue}`}>
      {children}
    </span>
  );
};

export default function LogisticsApp() {
  const [data, setData] = useState([]);
  const [fileName, setFileName] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fungsi untuk memparsing CSV
  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setLoading(true);
    setFileName(file.name);
    setError(null);

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target.result;
        const rows = text.split('\n');
        
        // Asumsi baris pertama adalah header
        // Struktur: city;postal_code;dist_banjaran;dist_kopo;dist_kalimalang;min_charge_banjaran;min_charge_kopo;min_charge_kalimalang;zone_category
        
        const parsedData = rows.slice(1).map((row, index) => {
          // Handle delimiter semicolon (;) sesuai file user
          const cols = row.split(';').map(c => c ? c.trim() : '');
          
          if (cols.length < 8) return null; // Skip baris rusak/kosong

          return {
            id: index,
            city: cols[0],
            postal_code: cols[1],
            distances: {
              banjaran: parseFloat(cols[2]) || 0,
              kopo: parseFloat(cols[3]) || 0,
              kalimalang: parseFloat(cols[4]) || 0,
            },
            charges: {
              banjaran: parseFloat(cols[5]) || 0,
              kopo: parseFloat(cols[6]) || 0,
              kalimalang: parseFloat(cols[7]) || 0,
            },
            zone: cols[8]
          };
        }).filter(item => item !== null);

        setData(parsedData);
      } catch (err) {
        setError("Gagal memproses file. Pastikan format CSV valid (delimiter ';').");
      } finally {
        setLoading(false);
      }
    };
    reader.readAsText(file);
  };

  // Filter Data
  const filteredData = useMemo(() => {
    if (!searchTerm) return data.slice(0, 50); // Batasi tampilan awal
    const lowerTerm = searchTerm.toLowerCase();
    return data.filter(item => 
      item.city.toLowerCase().includes(lowerTerm) || 
      item.postal_code.includes(lowerTerm)
    );
  }, [data, searchTerm]);

  // Format Mata Uang
  const formatIDR = (num) => {
    return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(num);
  };

  // Komponen Kartu Lokasi Tujuan
  const DestinationCard = ({ item }) => {
    // Cari yang termurah dan terdekat
    const costs = [
      { name: 'Banjaran', val: item.charges.banjaran, dist: item.distances.banjaran },
      { name: 'Kopo', val: item.charges.kopo, dist: item.distances.kopo },
      { name: 'Kalimalang', val: item.charges.kalimalang, dist: item.distances.kalimalang }
    ].filter(x => x.val > 0); // Filter out zero/invalid charges

    const minCost = Math.min(...costs.map(c => c.val));
    const minDist = Math.min(...costs.map(c => c.dist));

    return (
      <Card className="mb-4 overflow-hidden transition-all hover:shadow-md">
        <div className="p-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center flex-wrap gap-2">
          <div>
            <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <MapPin className="w-5 h-5 text-red-500" />
              {item.city}
            </h3>
            <p className="text-slate-500 text-sm ml-7">Kode Pos: <span className="font-mono font-medium text-slate-700">{item.postal_code}</span></p>
          </div>
          <div className="flex gap-2">
            <Badge color="slate">{item.zone || 'No Zone'}</Badge>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-slate-100">
          {/* Banjaran */}
          <OriginColumn 
            title="Banjaran" 
            dist={item.distances.banjaran} 
            cost={item.charges.banjaran} 
            isCheapest={item.charges.banjaran === minCost && item.charges.banjaran > 0}
            isClosest={item.distances.banjaran === minDist}
          />
          {/* Kopo */}
          <OriginColumn 
            title="Kopo" 
            dist={item.distances.kopo} 
            cost={item.charges.kopo} 
            isCheapest={item.charges.kopo === minCost && item.charges.kopo > 0}
            isClosest={item.distances.kopo === minDist}
          />
          {/* Kalimalang */}
          <OriginColumn 
            title="Kalimalang" 
            dist={item.distances.kalimalang} 
            cost={item.charges.kalimalang} 
            isCheapest={item.charges.kalimalang === minCost && item.charges.kalimalang > 0}
            isClosest={item.distances.kalimalang === minDist}
          />
        </div>
      </Card>
    );
  };

  const OriginColumn = ({ title, dist, cost, isCheapest, isClosest }) => (
    <div className={`p-4 ${isCheapest ? 'bg-emerald-50/30' : ''}`}>
      <div className="flex justify-between items-start mb-2">
        <span className="font-semibold text-slate-700">{title}</span>
        <div className="flex flex-col gap-1 items-end">
          {isCheapest && <Badge color="green">Termurah</Badge>}
          {isClosest && <Badge color="amber">Terdekat</Badge>}
        </div>
      </div>
      
      <div className="space-y-3 mt-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center text-slate-500 text-sm gap-2">
            <Truck className="w-4 h-4" />
            <span>Jarak</span>
          </div>
          <span className="font-medium text-slate-800">{dist} km</span>
        </div>
        
        <div className="flex items-center justify-between">
          <div className="flex items-center text-slate-500 text-sm gap-2">
            <DollarSign className="w-4 h-4" />
            <span>Min. Charge</span>
          </div>
          <span className={`font-bold ${isCheapest ? 'text-emerald-600' : 'text-slate-800'}`}>
            {cost ? formatIDR(cost) : '-'}
          </span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 font-sans">
      <div className="max-w-4xl mx-auto space-y-6">
        
        {/* Header */}
        <div className="text-center md:text-left flex flex-col md:flex-row justify-between items-center gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-slate-900 flex items-center gap-2 justify-center md:justify-start">
              <Package className="w-8 h-8 text-blue-600" />
              Cek Logistik & Ongkir
            </h1>
            <p className="text-slate-500 mt-1">Analisis jarak dan biaya pengiriman multi-origin</p>
          </div>
          
          {/* File Upload Section */}
          <div className="w-full md:w-auto">
            <label className="flex items-center gap-2 cursor-pointer bg-white border border-slate-300 hover:bg-slate-50 px-4 py-2 rounded-lg shadow-sm transition-colors group">
              <Upload className="w-4 h-4 text-slate-500 group-hover:text-blue-600" />
              <span className="text-sm font-medium text-slate-700">
                {fileName ? 'Ganti File CSV' : 'Upload distance.csv'}
              </span>
              <input 
                type="file" 
                accept=".csv"
                onChange={handleFileUpload} 
                className="hidden" 
              />
            </label>
          </div>
        </div>

        {/* Main Content */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            {error}
          </div>
        )}

        {data.length === 0 ? (
          /* Empty State */
          <div className="bg-white rounded-2xl border-2 border-dashed border-slate-200 p-12 text-center flex flex-col items-center justify-center">
            <div className="bg-blue-50 p-4 rounded-full mb-4">
              <FileText className="w-8 h-8 text-blue-500" />
            </div>
            <h3 className="text-lg font-semibold text-slate-800 mb-2">Belum ada data</h3>
            <p className="text-slate-500 max-w-md mx-auto mb-6">
              Silakan upload file <code>distance.csv</code> Anda untuk melihat perbandingan harga dan jarak dari Banjaran, Kopo, dan Kalimalang.
            </p>
            <label className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg font-medium cursor-pointer transition-colors shadow-lg shadow-blue-600/20">
              Upload File CSV Sekarang
              <input 
                type="file" 
                accept=".csv"
                onChange={handleFileUpload} 
                className="hidden" 
              />
            </label>
          </div>
        ) : (
          /* Data View */
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Search Bar */}
            <div className="sticky top-4 z-10 bg-white/80 backdrop-blur-md p-1 rounded-xl shadow-lg border border-slate-200/60 ring-1 ring-black/5">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Cari Kota atau Kode Pos (Contoh: Bandung atau 40191)..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-12 pr-4 py-3 bg-transparent outline-none text-slate-800 placeholder:text-slate-400 rounded-lg"
                />
              </div>
            </div>

            {/* Results Info */}
            <div className="flex justify-between items-center px-2">
              <span className="text-sm font-medium text-slate-500">
                Menampilkan {filteredData.length} hasil {fileName && `dari ${fileName}`}
              </span>
            </div>

            {/* List */}
            <div className="space-y-4 pb-12">
              {filteredData.length > 0 ? (
                filteredData.map((item) => (
                  <DestinationCard key={`${item.id}-${item.postal_code}`} item={item} />
                ))
              ) : (
                <div className="text-center py-12">
                  <p className="text-slate-400">Tidak ada lokasi yang cocok dengan pencarian "{searchTerm}"</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
