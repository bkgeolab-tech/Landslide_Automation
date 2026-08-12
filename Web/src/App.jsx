import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Play, RefreshCw, Download, Map as MapIcon } from 'lucide-react';
import { MapContainer, TileLayer, ImageOverlay, GeoJSON, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Lấy API_BASE từ biến môi trường (khi deploy) hoặc mặc định là localhost (khi dev)
const API_BASE = import.meta.env.VITE_API_BASE_URL // || 'http://localhost:8000';

// Helper component to adjust map view bounds
function MapUpdater({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) {
      map.fitBounds(bounds, { padding: [30, 30], animate: true });
    }
  }, [bounds, map]);
  return null;
}

const withCacheBuster = (url, ts) => {
  if (!url) return '';
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}t=${ts}`;
};

// Chuyển ISO UTC+0 sang giờ Việt Nam (UTC+7) dạng dễ đọc
const toVN = (isoStr) => {
  if (!isoStr) return null;
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleString('vi-VN', {
      timeZone: 'Asia/Ho_Chi_Minh',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    }) + ' (UTC+7)';
  } catch {
    return isoStr;
  }
};

// Hook để tải ảnh qua Axios (kèm header chống ngrok warning) và biến thành Object URL
function useImageFetcher(url) {
  const [imgUrl, setImgUrl] = useState(null);

  useEffect(() => {
    if (!url) {
      setImgUrl(null);
      return;
    }
    
    // Tải ảnh dưới dạng arraybuffer để ép kiểu thành Blob ảnh an toàn hơn
    axios.get(url, { 
      responseType: 'arraybuffer'
    })
      .then(res => {
        // Ép kiểu dữ liệu trả về thành Blob định dạng PNG
        const blob = new Blob([res.data], { type: 'image/png' });
        console.log("Tải ảnh thành công, kích thước:", blob.size, "bytes");
        const objectUrl = URL.createObjectURL(blob);
        setImgUrl(objectUrl);
      })
      .catch((err) => {
        console.error("Lỗi tải ảnh từ:", url, err);
        setImgUrl(null);
      });
      
    // Lưu ý: Đáng ra cần URL.revokeObjectURL nhưng để đơn giản ta tạm thời bỏ qua
  }, [url]);

  return imgUrl;
}

export default function App() {
  const [mode, setMode] = useState('realtime');
  const [forecastHour, setForecastHour] = useState(24);
  const [status, setStatus] = useState({ text: 'Sẵn sàng.', type: 'info' });
  const [loading, setLoading] = useState(false);
  const [timestamp, setTimestamp] = useState(Date.now());
  
  // Data state
  const [data, setData] = useState(null);
  const [overlayMeta, setOverlayMeta] = useState(null);
  const [valPoints, setValPoints] = useState(null);
  const [valMetrics, setValMetrics] = useState(null);
  const [opacity, setOpacity] = useState(0.75);

  // Validation toggles
  const [showPos, setShowPos] = useState(true);
  const [showNeg, setShowNeg] = useState(true);

  const endpoints = () => {
    if (mode === 'forecast') {
      return {
        latest: `${API_BASE}/api/forecast/latest?hours=${forecastHour}`,
        run: `${API_BASE}/api/forecast/run?hours=${forecastHour}`,
        overlayPng: `${API_BASE}/api/forecast/overlay/png?hours=${forecastHour}`,
        overlayMeta: `${API_BASE}/api/forecast/overlay/meta?hours=${forecastHour}`,
        webTif: `${API_BASE}/api/forecast/tif/web?hours=${forecastHour}`,
      };
    }
    if (mode === 'validation') {
      return {
        latest: `${API_BASE}/api/validation/2018/latest`,
        run: `${API_BASE}/api/validation/2018/run`,
        overlayPng: `${API_BASE}/api/validation/2018/overlay/png`,
        overlayMeta: `${API_BASE}/api/validation/2018/overlay/meta`,
        webTif: `${API_BASE}/api/validation/2018/tif/web`,
        rocPng: `${API_BASE}/api/validation/2018/roc/png`,
        points: `${API_BASE}/api/validation/2018/points`,
        roc: `${API_BASE}/api/validation/2018/roc`,
      };
    }
    return {
      latest: `${API_BASE}/api/realtime/latest`,
      run: `${API_BASE}/api/realtime/run?forecast_hour=6`,
      overlayPng: `${API_BASE}/api/realtime/overlay/png`,
      overlayMeta: `${API_BASE}/api/realtime/overlay/meta`,
      webTif: `${API_BASE}/api/realtime/tif/web`,
    };
  };

  const loadData = async () => {
    setLoading(true);
    setTimestamp(Date.now());
    setStatus({ text: 'Đang tải dữ liệu mới nhất...', type: 'info' });
    try {
      const ep = endpoints();
      
      // Fetch Latest JSON
      const resLatest = await axios.get(ep.latest).catch(() => null);
      if (resLatest?.data && resLatest.data.status === 'success') {
        setData(resLatest.data);
      } else {
        setData(null);
      }

      // Fetch Map Meta
      const resMeta = await axios.get(ep.overlayMeta).catch(() => null);
      if (resMeta?.data && resMeta.data.status === 'success') {
        const { south, west, north, east } = resMeta.data;
        if (south !== undefined) {
          setOverlayMeta({ bounds: [[south, west], [north, east]], crs: resMeta.data.crs });
        }
      } else {
        setOverlayMeta(null);
      }

      // Fetch Validation if mode is validation
      if (mode === 'validation') {
        const pRes = await axios.get(ep.points).catch(() => null);
        if (pRes?.data) setValPoints(pRes.data);
        const rocRes = await axios.get(ep.roc).catch(() => null);
        if (rocRes?.data) setValMetrics(rocRes.data);
      }

      setStatus({ text: 'Tải dữ liệu thành công.', type: 'success' });
    } catch (err) {
      setStatus({ text: `Lỗi tải dữ liệu: ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const runPipeline = async () => {
    setLoading(true);
    setStatus({ text: 'Đang chạy mô phỏng. Vui lòng chờ...', type: 'info' });
    try {
      const ep = endpoints();
      const res = await axios.post(ep.run);
      if (res.data?.status === 'success') {
        setStatus({ text: 'Chạy mô phỏng thành công!', type: 'success' });
        loadData();
      } else {
        setStatus({ text: 'Lỗi server khi chạy mô phỏng.', type: 'error' });
      }
    } catch (err) {
      setStatus({ text: `Lỗi API: ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [mode, forecastHour]);

  // Derived Info
  const summary = data?.risk?.summary || {};
  const rainfall = data?.rainfall || {};
  const ep = endpoints();

  // Load images via Axios hook to bypass ngrok warning
  const overlayImageUrl = useImageFetcher(overlayMeta ? withCacheBuster(ep.overlayPng, timestamp) : null);
  const rocImageUrl = useImageFetcher(mode === 'validation' ? withCacheBuster(ep.rocPng, timestamp) : null);

  // GeoJSON style & filter
  const pointStyle = (feature) => {
    const isPos = feature.properties.Label === 1;
    return {
      radius: isPos ? 5 : 4,
      fillColor: isPos ? '#ef4444' : '#3b82f6',
      color: isPos ? '#b91c1c' : '#1d4ed8',
      weight: 1,
      opacity: 1,
      fillOpacity: 0.85
    };
  };

  const filterPoints = (feature) => {
    const lbl = feature.properties.Label;
    if (lbl === 1 && showPos) return true;
    if (lbl === 0 && showNeg) return true;
    return false;
  };

  const onEachFeature = (feature, layer) => {
    const p = feature.properties.P_failure;
    const pStr = typeof p === 'number' ? p.toFixed(3) : '---';
    layer.bindPopup(`<b>Điểm Validation</b><br/>Label: ${feature.properties.Label}<br/>P_failure: ${pStr}`);
  };

  return (
    <div className="app-container">
      {/* SIDEBAR */}
      <aside className="sidebar glass">
        <div className="app-header">
          <h1 className="app-title" style={{ fontSize: '20px' }}>Landslide Hazard Early Warning Dashboard</h1>
          <p className="app-subtitle">Nha Trang, Vietnam · Hypercube LHS</p>
        </div>

        <div className="tabs">
          <button className={`tab-btn ${mode === 'realtime' ? 'active' : ''}`} onClick={() => setMode('realtime')}>Realtime</button>
          <button className={`tab-btn ${mode === 'forecast' ? 'active' : ''}`} onClick={() => setMode('forecast')}>Forecast</button>
          <button className={`tab-btn ${mode === 'validation' ? 'active' : ''}`} onClick={() => setMode('validation')}>Validation</button>
        </div>

        {status && (
          <div className={`status-banner ${status.type}`}>
            {status.text}
          </div>
        )}

        <div className="control-group">
          {mode === 'forecast' && (
            <>
              <label className="control-label">Forecast Horizon</label>
              <select value={forecastHour} onChange={e => setForecastHour(Number(e.target.value))}>
                <option value={6}>+6 Hours</option>
                <option value={12}>+12 Hours</option>
                <option value={24}>+24 Hours</option>
                <option value={48}>+48 Hours</option>
              </select>
            </>
          )}
        </div>

        <button className="btn btn-primary" onClick={runPipeline} disabled={loading}>
          <Play size={18} /> Chạy Mô Phỏng
        </button>
        
        <button className="btn btn-secondary" onClick={loadData} disabled={loading}>
          <RefreshCw size={18} /> Làm Mới Giao Diện
        </button>

        <a href={withCacheBuster(ep.overlayPng)} target="_blank" className="btn btn-download">
          <Download size={18} /> Tải Ảnh Bản Đồ (PNG)
        </a>
        <a href={ep.webTif} target="_blank" className="btn btn-download">
          <MapIcon size={18} /> Tải Dữ Liệu Gốc (GeoTIFF)
        </a>

        <div className="glass-card" style={{ marginTop: '24px' }}>
          <h3 className="control-label">Thông tin Sự kiện</h3>
          <div className="metrics-grid" style={{ marginBottom: '12px' }}>
            <div className="metric-item">
              <span className="metric-label">Kịch Bản / Sự Kiện</span>
              <span className="metric-value" style={{ fontSize: '16px' }}>{data?.event || '---'}</span>
            </div>
            <div className="metric-item">
              <span className="metric-label">Thời Điểm (Forecast/End)</span>
              <span className="metric-value" style={{ fontSize: '14px' }}>{toVN(rainfall.forecast_time) || toVN(rainfall.end_time) || '---'}</span>
            </div>
          </div>

          <h3 className="control-label">Thông tin Mưa</h3>
          <div className="metrics-grid" style={{ marginBottom: '12px' }}>
            <div className="metric-item">
              <span className="metric-label">Tổng Mưa</span>
              <span className="metric-value">{rainfall.accumulated_rainfall?.toFixed(2) || '---'} <span style={{fontSize: '12px'}}>mm</span></span>
            </div>
            <div className="metric-item">
              <span className="metric-label">Thời Gian</span>
              <span className="metric-value">{rainfall.duration || '---'} <span style={{fontSize: '12px'}}>h</span></span>
            </div>
            <div className="metric-item">
              <span className="metric-label">Cường Độ TB</span>
              <span className="metric-value">{rainfall.intensity?.toFixed(2) || '---'} <span style={{fontSize: '12px'}}>mm/h</span></span>
            </div>
            <div className="metric-item">
              <span className="metric-label">Nguồn Dữ Liệu</span>
              <span className="metric-value" style={{ fontSize: '14px' }}>{rainfall.source || '---'}</span>
            </div>
          </div>

          <h3 className="control-label">Đánh giá Nguy Cơ sạt lở</h3>
          <div className="metrics-grid">
            <div className="metric-item">
              <span className="metric-label">Max P_failure</span>
              <span className="metric-value">{summary.max_p_failure?.toFixed(3) || '---'}</span>
            </div>
            <div className="metric-item">
              <span className="metric-label">Mean P_failure</span>
              <span className="metric-value">{summary.mean_p_failure?.toFixed(3) || '---'}</span>
            </div>
            <div className="metric-item">
              <span className="metric-label">P {'>'} 30%</span>
              <span className="metric-value">{summary.percent_p_failure_gt_0_3?.toFixed(1) || '---'}%</span>
            </div>
            <div className="metric-item">
              <span className="metric-label">P {'>'} 50%</span>
              <span className="metric-value">{summary.percent_p_failure_gt_0_5?.toFixed(1) || '---'}%</span>
            </div>
            <div className="metric-item">
              <span className="metric-label">P {'>'} 70%</span>
              <span className="metric-value">{summary.percent_p_failure_gt_0_7?.toFixed(1) || '---'}%</span>
            </div>
            <div className="metric-item">
              <span className="metric-label">Tổng Diện Tích</span>
              <span className="metric-value">{summary.area_km2?.toFixed(2) || '---'} <span style={{fontSize: '12px'}}>km²</span></span>
            </div>
          </div>
          
          <label className="control-label" style={{marginTop: '16px'}}>Độ trong suốt bản đồ ({Math.round(opacity * 100)}%)</label>
          <div className="opacity-row">
            <input type="range" min="0" max="1" step="0.05" value={opacity} onChange={e => setOpacity(Number(e.target.value))} />
          </div>
        </div>

        {mode === 'validation' && (
          <div className="glass-card" style={{ marginTop: '16px' }}>
            <h3 className="control-label">ROC Validation 2018</h3>
            <div className="metrics-grid">
              <div className="metric-item">
                <span className="metric-label">AUC Model</span>
                <span className="metric-value">{valMetrics?.dynamic_pf_model?.auc?.toFixed(3) || '---'}</span>
              </div>
              <div className="metric-item">
                <span className="metric-label">AUC Paper</span>
                <span className="metric-value">{valMetrics?.static_station_model?.auc?.toFixed(3) || '---'}</span>
              </div>
            </div>
            {rocImageUrl && <img src={rocImageUrl} className="roc-image" alt="ROC Curve" />}
            
            <div style={{ marginTop: '12px' }}>
              <label style={{ display: 'flex', gap: '8px', alignItems: 'center', cursor: 'pointer', marginBottom: '8px' }}>
                <input type="checkbox" checked={showPos} onChange={e => setShowPos(e.target.checked)} />
                <span style={{ color: '#ef4444' }}>Điểm có sạt lở (Đỏ)</span>
              </label>
              <label style={{ display: 'flex', gap: '8px', alignItems: 'center', cursor: 'pointer' }}>
                <input type="checkbox" checked={showNeg} onChange={e => setShowNeg(e.target.checked)} />
                <span style={{ color: '#3b82f6' }}>Điểm an toàn (Xanh)</span>
              </label>
            </div>
          </div>
        )}
      </aside>

      {/* MAP VIEWER */}
      <main className="map-container">
        <MapContainer center={[12.17, 109.20]} zoom={12} style={{ width: '100%', height: '100%' }}>
          <TileLayer
            attribution='&copy; OpenStreetMap'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          {overlayMeta && overlayMeta.bounds && overlayImageUrl && (
            <>
              <MapUpdater bounds={overlayMeta.bounds} />
              <ImageOverlay
                url={overlayImageUrl}
                bounds={overlayMeta.bounds}
                opacity={opacity}
                zIndex={10}
              />
            </>
          )}

          {mode === 'validation' && valPoints && (
            <GeoJSON 
              data={valPoints} 
              pointToLayer={(feature, latlng) => {
                return L.circleMarker(latlng, pointStyle(feature));
              }}
              filter={filterPoints}
              onEachFeature={onEachFeature}
            />
          )}
        </MapContainer>
        
        {overlayMeta && overlayMeta.bounds && (
          <div className="map-meta-float glass">
            Bounds: {overlayMeta.bounds[0][0].toFixed(4)}, {overlayMeta.bounds[0][1].toFixed(4)} <br/>
            to {overlayMeta.bounds[1][0].toFixed(4)}, {overlayMeta.bounds[1][1].toFixed(4)}
          </div>
        )}
      </main>
    </div>
  );
}
