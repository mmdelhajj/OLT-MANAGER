import React, { useState, useEffect, useCallback, useRef } from 'react';
import * as api from './api';

// VSOL OLT Models with PON port counts
const VSOL_OLT_MODELS = {
  // GPON (1 PON)
  'V1600GS': 1,
  'V1600GS-F': 1,
  'V1600GS-ZF': 1,
  'V1600GS-O32': 1,

  // GPON (2 PON)
  'V1600GT': 2,

  // GPON (4 PON)
  'V1600G0': 4,
  'V1600G0-B': 4,

  // GPON (8 PON)
  'V1600G1': 8,
  'V1600G1-B': 8,
  'V1600G1-R': 8,
  'V1600G1WEO': 8,
  'V1600G1WEO-B': 8,

  // GPON (16 PON)
  'V1600G2': 16,
  'V1600G2-B': 16,
  'V1600G2-R': 16,

  // EPON (2 PON)
  'V1601E02-DP': 2,
  'V1600D2': 2,
  'V1600D2-L': 2,

  // EPON (4 PON)
  'V1600D-MINI': 4,
  'V1601E04-DP': 4,
  'V1600D4': 4,
  'V1600D4-L': 4,
  'V1600D4-DP': 4,

  // EPON (8 PON)
  'V1600D8': 8,

  // EPON (16 PON)
  'V1600D16': 16,

  // XGS-PON / 10G (2 PON)
  'V1600XG02': 2,
  'V1600XG02-W': 2,

  // XGS-PON / 10G (8 PON)
  'V3600G1': 8,
  'V3600G1-C': 8,
  'V3600D8': 8,

  // Chassis (32+ PON)
  'V5600X2': 32,
  'V5600X7': 112,

  // Other (manual entry)
  'Other': 0,
};

// Build v4 - Professional Material Design UI
// Login Page Component - Premium Enterprise Design
function LoginPage({ onLogin, pageName }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const response = await api.login(username, password);
      localStorage.setItem('token', response.data.token);
      localStorage.setItem('user', JSON.stringify(response.data.user));
      onLogin(response.data.user);
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative overflow-hidden flex items-center justify-center p-4">
      {/* Animated Background */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">
        <div className="absolute inset-0 opacity-30">
          <div className="absolute top-0 -left-4 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-xl animate-pulse"></div>
          <div className="absolute top-0 -right-4 w-72 h-72 bg-cyan-500 rounded-full mix-blend-multiply filter blur-xl animate-pulse" style={{animationDelay: '2s'}}></div>
          <div className="absolute -bottom-8 left-20 w-72 h-72 bg-blue-500 rounded-full mix-blend-multiply filter blur-xl animate-pulse" style={{animationDelay: '4s'}}></div>
        </div>
        {/* Network Grid Pattern */}
        <div className="absolute inset-0 opacity-10" style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, rgba(255,255,255,0.3) 1px, transparent 0)`,
          backgroundSize: '40px 40px'
        }}></div>
      </div>

      {/* Login Card */}
      <div className="relative w-full max-w-md">
        {/* Glow Effect */}
        <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-500 rounded-2xl blur-lg opacity-40"></div>

        <div className="relative bg-white/95 backdrop-blur-xl p-8 rounded-2xl shadow-2xl border border-white/20">
          {/* Logo & Header */}
          <div className="text-center mb-8">
            <div className="relative inline-block">
              <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-500/30 transform rotate-3 hover:rotate-0 transition-transform duration-300">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
                </svg>
              </div>
              <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-400 rounded-full border-2 border-white animate-pulse"></div>
            </div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent">
              {pageName || 'OLT Manager'}
            </h1>
            <p className="text-gray-500 mt-2 text-sm">Fiber Network Management System</p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border-l-4 border-red-500 rounded-r-lg flex items-center gap-3 animate-shake">
              <svg className="w-5 h-5 text-red-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <span className="text-red-700 text-sm font-medium">{error}</span>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-gray-700">Username</label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <svg className="w-5 h-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
                <input
                  type="text"
                  required
                  className="w-full pl-12 pr-4 py-3.5 bg-gray-50 border-2 border-gray-200 rounded-xl focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 transition-all duration-200 outline-none text-gray-800 placeholder-gray-400"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-semibold text-gray-700">Password</label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <svg className="w-5 h-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  className="w-full pl-12 pr-12 py-3.5 bg-gray-50 border-2 border-gray-200 rounded-xl focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 transition-all duration-200 outline-none text-gray-800 placeholder-gray-400"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  title={showPassword ? "Hide password" : "Show password"}
                  className="absolute inset-y-0 right-0 pr-4 flex items-center text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-4 px-4 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-xl hover:from-blue-700 hover:to-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed font-semibold shadow-lg shadow-blue-500/30 hover:shadow-blue-500/40 transform hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </>
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-8 pt-6 border-t border-gray-100 text-center">
            <p className="text-xs text-gray-400">
              GPON Fiber Network Management
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Stats Card Component - Enterprise Pro Design
function StatsCard({ title, value, subValue, color, icon, trend, trendValue, footerText }) {
  const colorConfig = {
    blue: { iconBg: 'bg-blue-50', iconColor: 'text-blue-600', trendUp: 'text-emerald-600', trendDown: 'text-red-600' },
    green: { iconBg: 'bg-emerald-50', iconColor: 'text-emerald-600', trendUp: 'text-emerald-600', trendDown: 'text-red-600' },
    red: { iconBg: 'bg-red-50', iconColor: 'text-red-600', trendUp: 'text-emerald-600', trendDown: 'text-red-600' },
    yellow: { iconBg: 'bg-amber-50', iconColor: 'text-amber-600', trendUp: 'text-emerald-600', trendDown: 'text-red-600' },
    purple: { iconBg: 'bg-purple-50', iconColor: 'text-purple-600', trendUp: 'text-emerald-600', trendDown: 'text-red-600' },
    gray: { iconBg: 'bg-gray-100', iconColor: 'text-gray-600', trendUp: 'text-emerald-600', trendDown: 'text-red-600' },
    indigo: { iconBg: 'bg-indigo-50', iconColor: 'text-indigo-600', trendUp: 'text-emerald-600', trendDown: 'text-red-600' },
    cyan: { iconBg: 'bg-cyan-50', iconColor: 'text-cyan-600', trendUp: 'text-emerald-600', trendDown: 'text-red-600' },
  };

  const icons = {
    olt: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
    ),
    onu: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
    ),
    online: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    ),
    offline: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
    ),
    region: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
    ),
  };

  const cfg = colorConfig[color] || colorConfig.blue;

  return (
    <div className="bg-white rounded-xl p-5 border border-[#e8eaed] hover:shadow-sm transition-shadow duration-200">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-[#4b5563] font-medium mb-1">{title}</p>
          <div className="flex items-baseline gap-2">
            <p className="text-3xl font-semibold text-[#111827] tabular-nums">{value}</p>
            {trendValue && (
              <span className={`text-sm font-medium ${trend === 'up' ? cfg.trendUp : cfg.trendDown}`}>
                {trend === 'up' ? '+' : ''}{trendValue}
              </span>
            )}
          </div>
          {subValue && (
            <p className="text-sm text-[#9ca3af] mt-1">{subValue}</p>
          )}
        </div>
        <div className={`${cfg.iconBg} rounded-lg p-3`}>
          <svg className={`w-6 h-6 ${cfg.iconColor}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {icons[icon] || icons.olt}
          </svg>
        </div>
      </div>
      {footerText && (
        <div className="mt-4 pt-3 border-t border-[#e8eaed]">
          <p className="text-xs text-[#9ca3af]">{footerText}</p>
        </div>
      )}
    </div>
  );
}

// Status Badge Component - Enterprise Pro Pill Style
function StatusBadge({ online }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full ${
      online
        ? 'bg-[#d1fae5] text-[#059669]'
        : 'bg-[#fee2e2] text-[#dc2626]'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${online ? 'bg-[#059669]' : 'bg-[#dc2626]'}`}></span>
      {online ? 'Online' : 'Offline'}
    </span>
  );
}

// Modal Component - Modern Design
function Modal({ isOpen, onClose, title, children, size = 'md' }) {
  if (!isOpen) return null;

  const sizes = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
  };

  return (
    <div className="fixed inset-0 bg-gray-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fadeIn">
      <div className={`relative bg-white rounded-2xl shadow-2xl w-full ${sizes[size]} max-h-[90vh] overflow-hidden transform transition-all animate-slideUp`}>
        {/* Header with gradient accent */}
        <div className="relative bg-gradient-to-r from-gray-50 to-white border-b border-gray-100">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 via-cyan-500 to-blue-500"></div>
          <div className="flex justify-between items-center p-5">
            <h2 className="text-xl font-bold text-gray-800">{title}</h2>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-all duration-200"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        <div className="p-5 overflow-y-auto max-h-[calc(90vh-80px)]">{children}</div>
      </div>
    </div>
  );
}

// Image Preview Modal Component (Lightbox)
function ImagePreviewModal({ isOpen, onClose, images, initialIndex = 0, title }) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);

  useEffect(() => {
    setCurrentIndex(initialIndex);
  }, [initialIndex, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft') setCurrentIndex((prev) => (prev > 0 ? prev - 1 : images.length - 1));
      if (e.key === 'ArrowRight') setCurrentIndex((prev) => (prev < images.length - 1 ? prev + 1 : 0));
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, images.length, onClose]);

  if (!isOpen || !images || images.length === 0) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center z-50" onClick={onClose}>
      <div className="relative max-w-4xl max-h-[90vh] w-full mx-4" onClick={(e) => e.stopPropagation()}>
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute -top-10 right-0 text-white hover:text-gray-300 z-10"
        >
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Title */}
        {title && (
          <div className="absolute -top-10 left-0 text-white text-lg font-medium">
            {title}
          </div>
        )}

        {/* Main image */}
        <div className="flex items-center justify-center">
          <img
            src={images[currentIndex]}
            alt={`Preview ${currentIndex + 1}`}
            className="max-h-[80vh] max-w-full object-contain rounded-lg"
          />
        </div>

        {/* Navigation arrows */}
        {images.length > 1 && (
          <>
            <button
              onClick={() => setCurrentIndex((prev) => (prev > 0 ? prev - 1 : images.length - 1))}
              className="absolute left-2 top-1/2 -translate-y-1/2 bg-black bg-opacity-50 hover:bg-opacity-75 text-white p-2 rounded-full"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <button
              onClick={() => setCurrentIndex((prev) => (prev < images.length - 1 ? prev + 1 : 0))}
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-black bg-opacity-50 hover:bg-opacity-75 text-white p-2 rounded-full"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </>
        )}

        {/* Image counter */}
        {images.length > 1 && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black bg-opacity-50 text-white px-3 py-1 rounded-full text-sm">
            {currentIndex + 1} / {images.length}
          </div>
        )}

        {/* Thumbnails */}
        {images.length > 1 && (
          <div className="flex justify-center mt-4 gap-2">
            {images.map((img, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentIndex(idx)}
                className={`w-16 h-16 rounded-lg overflow-hidden border-2 ${
                  idx === currentIndex ? 'border-blue-500' : 'border-transparent opacity-60 hover:opacity-100'
                }`}
              >
                <img src={img} alt={`Thumb ${idx + 1}`} className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Add OLT Modal Component
function AddOLTModal({ isOpen, onClose, onSubmit, regions }) {
  const [formData, setFormData] = useState({
    name: '',
    ip_address: '',
    username: 'admin',
    password: '',
    snmp_community: 'public',
    model: '',
    pon_ports: 8,
    region_id: '',
  });
  const [loading, setLoading] = useState(false);
  const [ponPortsReadOnly, setPonPortsReadOnly] = useState(false);

  const handleModelChange = (model) => {
    if (model && model !== 'Other' && VSOL_OLT_MODELS[model]) {
      setFormData({ ...formData, model, pon_ports: VSOL_OLT_MODELS[model] });
      setPonPortsReadOnly(true);
    } else {
      setFormData({ ...formData, model, pon_ports: model === 'Other' ? '' : 8 });
      setPonPortsReadOnly(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = { ...formData };
      if (data.region_id === '') delete data.region_id;
      else data.region_id = parseInt(data.region_id);
      await onSubmit(data);
      setFormData({ name: '', ip_address: '', username: 'admin', password: '', snmp_community: 'public', model: '', pon_ports: 8, region_id: '' });
      setPonPortsReadOnly(false);
      onClose();
    } catch (error) {
      alert('Failed to add OLT: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add New OLT" size="lg">
      <form onSubmit={handleSubmit}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input
              type="text"
              required
              className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="OLT-1"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">IP Address *</label>
            <input
              type="text"
              required
              pattern="^(\d{1,3}\.){3}\d{1,3}$"
              className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
              value={formData.ip_address}
              onChange={(e) => setFormData({ ...formData, ip_address: e.target.value })}
              placeholder="10.10.10.1"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">OLT Username *</label>
              <input
                type="text"
                required
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                placeholder="admin"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">OLT Password *</label>
              <input
                type="password"
                required
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder="OLT password"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">SNMP Community</label>
            <input
              type="text"
              className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
              value={formData.snmp_community}
              onChange={(e) => setFormData({ ...formData, snmp_community: e.target.value })}
              placeholder="public"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
              <select
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
                value={formData.model}
                onChange={(e) => handleModelChange(e.target.value)}
              >
                <option value="">Select Model</option>
                <optgroup label="GPON - 1 PON">
                  <option value="V1600GS">V1600GS</option>
                  <option value="V1600GS-F">V1600GS-F</option>
                  <option value="V1600GS-ZF">V1600GS-ZF</option>
                  <option value="V1600GS-O32">V1600GS-O32</option>
                </optgroup>
                <optgroup label="GPON - 2 PON">
                  <option value="V1600GT">V1600GT</option>
                </optgroup>
                <optgroup label="GPON - 4 PON">
                  <option value="V1600G0">V1600G0</option>
                  <option value="V1600G0-B">V1600G0-B</option>
                </optgroup>
                <optgroup label="GPON - 8 PON">
                  <option value="V1600G1">V1600G1</option>
                  <option value="V1600G1-B">V1600G1-B</option>
                  <option value="V1600G1-R">V1600G1-R</option>
                  <option value="V1600G1WEO">V1600G1WEO</option>
                  <option value="V1600G1WEO-B">V1600G1WEO-B</option>
                </optgroup>
                <optgroup label="GPON - 16 PON">
                  <option value="V1600G2">V1600G2</option>
                  <option value="V1600G2-B">V1600G2-B</option>
                  <option value="V1600G2-R">V1600G2-R</option>
                </optgroup>
                <optgroup label="EPON - 2 PON">
                  <option value="V1601E02-DP">V1601E02-DP</option>
                  <option value="V1600D2">V1600D2</option>
                  <option value="V1600D2-L">V1600D2-L</option>
                </optgroup>
                <optgroup label="EPON - 4 PON">
                  <option value="V1600D-MINI">V1600D-MINI</option>
                  <option value="V1601E04-DP">V1601E04-DP</option>
                  <option value="V1600D4">V1600D4</option>
                  <option value="V1600D4-L">V1600D4-L</option>
                  <option value="V1600D4-DP">V1600D4-DP</option>
                </optgroup>
                <optgroup label="EPON - 8 PON">
                  <option value="V1600D8">V1600D8</option>
                </optgroup>
                <optgroup label="EPON - 16 PON">
                  <option value="V1600D16">V1600D16</option>
                </optgroup>
                <optgroup label="XGS-PON 10G - 2 PON">
                  <option value="V1600XG02">V1600XG02</option>
                  <option value="V1600XG02-W">V1600XG02-W</option>
                </optgroup>
                <optgroup label="XGS-PON 10G - 8 PON">
                  <option value="V3600G1">V3600G1</option>
                  <option value="V3600G1-C">V3600G1-C</option>
                  <option value="V3600D8">V3600D8</option>
                </optgroup>
                <optgroup label="Chassis">
                  <option value="V5600X2">V5600X2 (32 PON)</option>
                  <option value="V5600X7">V5600X7 (112 PON)</option>
                </optgroup>
                <optgroup label="Custom">
                  <option value="Other">Other</option>
                </optgroup>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">PON Ports</label>
              <input
                type="number"
                min="1"
                max="128"
                required
                className={`w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500 ${ponPortsReadOnly ? 'bg-gray-100 text-gray-600' : ''}`}
                value={formData.pon_ports}
                onChange={(e) => setFormData({ ...formData, pon_ports: parseInt(e.target.value) || '' })}
                readOnly={ponPortsReadOnly}
              />
              {ponPortsReadOnly && <p className="text-xs text-gray-500 mt-1">Auto-filled from model</p>}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Region</label>
            <select
              className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
              value={formData.region_id}
              onChange={(e) => setFormData({ ...formData, region_id: e.target.value })}
            >
              <option value="">No Region</option>
              {regions.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="mt-6 flex justify-end space-x-3">
          <button type="button" onClick={onClose} className="px-4 py-2 border rounded-lg text-gray-700 hover:bg-gray-50">
            Cancel
          </button>
          <button type="submit" disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {loading ? 'Adding...' : 'Add OLT'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// Edit ONU Modal with Map and Image Upload
function EditONUModal({ isOpen, onClose, onu, onSubmit, onImageUpload, onImageDelete, regions }) {
  const [formData, setFormData] = useState({
    description: '',
    latitude: '',
    longitude: '',
    address: '',
    region_id: '',
  });
  const [loading, setLoading] = useState(false);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageUrls, setImageUrls] = useState([]);

  useEffect(() => {
    if (onu) {
      setFormData({
        description: onu.description || '',
        latitude: onu.latitude || '',
        longitude: onu.longitude || '',
        address: onu.address || '',
        region_id: onu.region_id || '',
      });
      // Use image_urls if available, otherwise fall back to single image_url
      setImageUrls(onu.image_urls || (onu.image_url ? [onu.image_url] : []));
    }
  }, [onu]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = {
        description: formData.description || null,
        latitude: formData.latitude ? parseFloat(formData.latitude) : null,
        longitude: formData.longitude ? parseFloat(formData.longitude) : null,
        address: formData.address || null,
        region_id: formData.region_id ? parseInt(formData.region_id) : null,
      };
      await onSubmit(onu.id, data);
      onClose();
    } catch (error) {
      alert('Failed to update ONU: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const openGoogleMaps = () => {
    if (formData.latitude && formData.longitude) {
      window.open(`https://www.google.com/maps?q=${formData.latitude},${formData.longitude}`, '_blank');
    }
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      alert('Image must be less than 5MB');
      return;
    }

    if (imageUrls.length >= 3) {
      alert('Maximum 3 images allowed. Delete an existing image first.');
      return;
    }

    setImageLoading(true);
    try {
      const result = await onImageUpload(onu.id, file);
      setImageUrls(result.image_urls || [...imageUrls, result.image_url]);
    } catch (error) {
      alert('Failed to upload image: ' + (error.response?.data?.detail || error.message));
    } finally {
      setImageLoading(false);
    }
  };

  const handleImageDelete = async (imageIndex) => {
    if (!window.confirm('Delete this image?')) return;

    setImageLoading(true);
    try {
      const result = await onImageDelete(onu.id, imageIndex);
      setImageUrls(result.image_urls || []);
    } catch (error) {
      alert('Failed to delete image: ' + (error.response?.data?.detail || error.message));
    } finally {
      setImageLoading(false);
    }
  };

  if (!onu) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Edit ONU" size="lg">
      <div className="mb-4 p-3 bg-gray-50 rounded-lg">
        <p className="text-sm"><strong>MAC:</strong> {onu.mac_address}</p>
        <p className="text-sm"><strong>Port:</strong> 0/{onu.pon_port}:{onu.onu_id}</p>
        <p className="text-sm"><strong>OLT:</strong> {onu.olt_name}</p>
      </div>
      <form onSubmit={handleSubmit}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Customer Name / Description</label>
            <input
              type="text"
              className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Customer name or description"
            />
            <p className="text-xs text-gray-500 mt-1">This will be synced to the OLT device</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Region</label>
            <div className="relative">
              <select
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 pl-10 focus:ring-2 focus:ring-blue-500 appearance-none"
                value={formData.region_id}
                onChange={(e) => setFormData({ ...formData, region_id: e.target.value })}
              >
                <option value="">No Region</option>
                {regions && regions.map(region => (
                  <option key={region.id} value={region.id}>
                    {region.name}
                  </option>
                ))}
              </select>
              {/* Color indicator for selected region */}
              <div
                className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 rounded-full border border-gray-300"
                style={{
                  backgroundColor: formData.region_id
                    ? (regions?.find(r => r.id === parseInt(formData.region_id))?.color || '#E5E7EB')
                    : '#E5E7EB'
                }}
              />
              {/* Dropdown arrow */}
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2 pointer-events-none">
                <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Latitude</label>
              <input
                type="number"
                step="any"
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
                value={formData.latitude}
                onChange={(e) => setFormData({ ...formData, latitude: e.target.value })}
                placeholder="24.7136"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Longitude</label>
              <input
                type="number"
                step="any"
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
                value={formData.longitude}
                onChange={(e) => setFormData({ ...formData, longitude: e.target.value })}
                placeholder="46.6753"
              />
            </div>
          </div>
          {formData.latitude && formData.longitude && (
            <button
              type="button"
              onClick={openGoogleMaps}
              className="w-full py-2 px-4 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 flex items-center justify-center"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Open in Google Maps
            </button>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
            <textarea
              className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
              rows="2"
              value={formData.address}
              onChange={(e) => setFormData({ ...formData, address: e.target.value })}
              placeholder="Street address, building, etc."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Building/Location Images ({imageUrls.length}/3)</label>
            {/* Display existing images */}
            {imageUrls.length > 0 && (
              <div className="grid grid-cols-3 gap-2 mb-3">
                {imageUrls.map((url, index) => (
                  <div key={index} className="relative">
                    <img
                      src={`${process.env.REACT_APP_API_URL || ''}${url}`}
                      alt={`Building ${index + 1}`}
                      className="w-full h-24 object-cover rounded-lg border"
                    />
                    <button
                      type="button"
                      onClick={() => handleImageDelete(index)}
                      disabled={imageLoading}
                      className="absolute top-1 right-1 p-1 bg-red-500 text-white rounded-full hover:bg-red-600 disabled:opacity-50"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
            {/* Upload button (only if less than 3 images) */}
            {imageUrls.length < 3 && (
              <div className="flex items-center justify-center w-full">
                <label className="flex flex-col items-center justify-center w-full h-24 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100">
                  <div className="flex flex-col items-center justify-center py-2">
                    {imageLoading ? (
                      <div className="text-gray-500">Uploading...</div>
                    ) : (
                      <>
                        <svg className="w-6 h-6 mb-1 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                        </svg>
                        <p className="text-xs text-gray-500">Add image ({3 - imageUrls.length} remaining)</p>
                        <p className="text-xs text-gray-400">JPG, PNG, GIF up to 5MB</p>
                      </>
                    )}
                  </div>
                  <input type="file" className="hidden" accept="image/*" onChange={handleImageUpload} disabled={imageLoading} />
                </label>
              </div>
            )}
            {imageLoading && (
              <div className="mt-2 text-center text-gray-500">Processing...</div>
            )}
          </div>
        </div>
        <div className="mt-6 flex justify-end space-x-3">
          <button type="button" onClick={onClose} className="px-4 py-2 border rounded-lg text-gray-700 hover:bg-gray-50">
            Cancel
          </button>
          <button type="submit" disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {loading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// Region Modal
function RegionModal({ isOpen, onClose, region, onSubmit }) {
  const [formData, setFormData] = useState({ name: '', description: '', color: '#3B82F6' });
  const [loading, setLoading] = useState(false);

  // Preset colors for easy selection
  const presetColors = [
    '#3B82F6', // Blue
    '#10B981', // Green
    '#F59E0B', // Amber
    '#EF4444', // Red
    '#8B5CF6', // Purple
    '#EC4899', // Pink
    '#06B6D4', // Cyan
    '#F97316', // Orange
  ];

  useEffect(() => {
    if (region) {
      setFormData({
        name: region.name || '',
        description: region.description || '',
        color: region.color || '#3B82F6',
      });
    } else {
      setFormData({ name: '', description: '', color: '#3B82F6' });
    }
  }, [region]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = {
        name: formData.name,
        description: formData.description || null,
        color: formData.color,
      };
      await onSubmit(data, region?.id);
      onClose();
    } catch (error) {
      alert('Failed to save region: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={region ? 'Edit Region' : 'Add Region'}>
      <form onSubmit={handleSubmit}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input
              type="text"
              required
              className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Region name"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
              rows="2"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Optional description"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Color</label>
            <div className="flex items-center gap-3">
              <div className="flex gap-2 flex-wrap">
                {presetColors.map((color) => (
                  <button
                    key={color}
                    type="button"
                    onClick={() => setFormData({ ...formData, color })}
                    className={`w-8 h-8 rounded-full border-2 transition-transform hover:scale-110 ${
                      formData.color === color ? 'border-gray-800 ring-2 ring-offset-2 ring-gray-400' : 'border-gray-300'
                    }`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
              <input
                type="color"
                value={formData.color}
                onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                className="w-10 h-10 rounded cursor-pointer border-0"
                title="Custom color"
              />
            </div>
          </div>
        </div>
        <div className="mt-6 flex justify-end space-x-3">
          <button type="button" onClick={onClose} className="px-4 py-2 border rounded-lg text-gray-700 hover:bg-gray-50">
            Cancel
          </button>
          <button type="submit" disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {loading ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// User Modal
function UserModal({ isOpen, onClose, user, onSubmit, olts }) {
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    full_name: '',
    role: 'operator',
    is_active: true,
    assigned_olt_ids: [],
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      setFormData({
        username: user.username || '',
        password: '',
        full_name: user.full_name || '',
        role: user.role || 'operator',
        is_active: user.is_active !== false,
        assigned_olt_ids: user.assigned_olt_ids || [],
      });
    } else {
      setFormData({ username: '', password: '', full_name: '', role: 'operator', is_active: true, assigned_olt_ids: [] });
    }
  }, [user]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = { ...formData };
      if (user && !data.password) delete data.password;
      await onSubmit(data, user?.id);
      onClose();
    } catch (error) {
      alert('Failed to save user: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const toggleOLT = (oltId) => {
    const ids = formData.assigned_olt_ids.includes(oltId)
      ? formData.assigned_olt_ids.filter((id) => id !== oltId)
      : [...formData.assigned_olt_ids, oltId];
    setFormData({ ...formData, assigned_olt_ids: ids });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={user ? 'Edit User' : 'Add User'} size="lg">
      <form onSubmit={handleSubmit}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
            <input
              type="text"
              required
              disabled={!!user}
              className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Password {user ? '(leave blank to keep current)' : '*'}
            </label>
            <input
              type="password"
              required={!user}
              className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              type="text"
              className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
              <select
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              >
                <option value="admin">Admin</option>
                <option value="operator">Operator</option>
              </select>
            </div>
            <div className="flex items-center pt-6">
              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  className="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                />
                <span className="ml-2 text-sm text-gray-700">Active</span>
              </label>
            </div>
          </div>
          {formData.role === 'operator' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Assigned OLTs</label>
              <p className="text-xs text-gray-500 mb-2">Operators can only see ONUs from assigned OLTs</p>
              <div className="border rounded-lg p-3 max-h-40 overflow-y-auto space-y-2">
                {olts.map((olt) => (
                  <label key={olt.id} className="flex items-center cursor-pointer hover:bg-gray-50 p-1 rounded">
                    <input
                      type="checkbox"
                      className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      checked={formData.assigned_olt_ids.includes(olt.id)}
                      onChange={() => toggleOLT(olt.id)}
                    />
                    <span className="ml-2 text-sm">{olt.name} ({olt.ip_address})</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="mt-6 flex justify-end space-x-3">
          <button type="button" onClick={onClose} className="px-4 py-2 border rounded-lg text-gray-700 hover:bg-gray-50">
            Cancel
          </button>
          <button type="submit" disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {loading ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// Settings Modal
function SettingsModal({ isOpen, onClose, settings, onSubmit, onChangePassword }) {
  const [formData, setFormData] = useState({
    system_name: 'OLT Manager',
    page_name: '',
    polling_interval: 300,
    whatsapp_enabled: false,
    whatsapp_api_url: '',
    whatsapp_secret: '',
    whatsapp_account: '',
    whatsapp_recipients: [],
    trap_enabled: true,
    trap_port: 162,
  });
  const [passwordData, setPasswordData] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testingRecipient, setTestingRecipient] = useState(null);
  const [activeTab, setActiveTab] = useState('general');
  const [newRecipient, setNewRecipient] = useState({ name: '', phone: '' });

  useEffect(() => {
    if (settings) {
      let recipients = [];
      try {
        if (settings.whatsapp_recipients) {
          recipients = JSON.parse(settings.whatsapp_recipients);
          if (!Array.isArray(recipients)) recipients = [];
        }
      } catch { recipients = []; }

      setFormData({
        system_name: settings.system_name || 'OLT Manager',
        page_name: settings.page_name || 'OLT Manager',
        polling_interval: settings.polling_interval || 300,
        whatsapp_enabled: String(settings.whatsapp_enabled).toLowerCase() === 'true' || settings.whatsapp_enabled === true,
        whatsapp_api_url: settings.whatsapp_api_url || 'https://proxsms.com/api/send/whatsapp',
        whatsapp_secret: settings.whatsapp_secret || '',
        whatsapp_account: settings.whatsapp_account || '',
        whatsapp_recipients: recipients,
        trap_enabled: String(settings.trap_enabled).toLowerCase() === 'true' || settings.trap_enabled === true,
        trap_port: settings.trap_port || 162,
      });
    }
  }, [settings]);

  const addRecipient = () => {
    if (!newRecipient.name.trim() || !newRecipient.phone.trim()) {
      alert('Please enter both name and phone number');
      return;
    }
    setFormData({
      ...formData,
      whatsapp_recipients: [...formData.whatsapp_recipients, { ...newRecipient }]
    });
    setNewRecipient({ name: '', phone: '' });
  };

  const removeRecipient = (index) => {
    const updated = formData.whatsapp_recipients.filter((_, i) => i !== index);
    setFormData({ ...formData, whatsapp_recipients: updated });
  };

  const handleTestWhatsApp = async (recipientPhone, recipientName, index) => {
    if (!formData.whatsapp_secret || !formData.whatsapp_account) {
      alert('Please fill in API settings first');
      return;
    }
    setTestingRecipient(index);
    try {
      const response = await fetch('/api/whatsapp/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          api_url: formData.whatsapp_api_url,
          secret: formData.whatsapp_secret,
          account: formData.whatsapp_account,
          recipient: recipientPhone
        })
      });
      const data = await response.json();
      if (response.ok) {
        alert(`Test message sent to ${recipientName}!`);
      } else {
        alert('Failed to send test message: ' + (data.detail || data.message || 'Unknown error'));
      }
    } catch (error) {
      alert('Error sending test message: ' + error.message);
    } finally {
      setTestingRecipient(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      // Serialize recipients as JSON for backend storage
      const dataToSave = {
        ...formData,
        whatsapp_recipients: JSON.stringify(formData.whatsapp_recipients)
      };
      await onSubmit(dataToSave);
      alert('Settings saved successfully');
    } catch (error) {
      alert('Failed to save settings: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    if (passwordData.new_password !== passwordData.confirm_password) {
      alert('Passwords do not match');
      return;
    }
    setLoading(true);
    try {
      await onChangePassword({
        current_password: passwordData.current_password,
        new_password: passwordData.new_password,
      });
      alert('Password changed successfully');
      setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
    } catch (error) {
      alert('Failed to change password: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Settings" size="lg">
      <div className="flex border-b mb-4 overflow-x-auto">
        <button
          className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'general' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
          onClick={() => setActiveTab('general')}
        >
          General
        </button>
        <button
          className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'whatsapp' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
          onClick={() => setActiveTab('whatsapp')}
        >
          WhatsApp
        </button>
        <button
          className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'password' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
          onClick={() => setActiveTab('password')}
        >
          Password
        </button>
      </div>

      {activeTab === 'general' && (
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">System Name</label>
              <input
                type="text"
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
                value={formData.system_name}
                onChange={(e) => setFormData({ ...formData, system_name: e.target.value })}
                placeholder="OLT Manager"
              />
              <p className="text-xs text-gray-500 mt-1">Name displayed in header and browser title</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Polling Interval (seconds)</label>
              <input
                type="number"
                min="60"
                max="3600"
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
                value={formData.polling_interval}
                onChange={(e) => setFormData({ ...formData, polling_interval: parseInt(e.target.value) })}
              />
              <p className="text-xs text-gray-500 mt-1">How often to poll OLTs for ONU status (60-3600 seconds)</p>
            </div>
          </div>
          <div className="mt-6 flex justify-end">
            <button type="submit" disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
              {loading ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </form>
      )}

      {activeTab === 'whatsapp' && (
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            {/* Enable/Disable Toggle - Always visible at top */}
            <div className="flex items-center justify-between p-4 bg-gradient-to-r from-green-50 to-green-100 rounded-xl border border-green-200">
              <div className="flex items-center">
                <div className="w-12 h-12 bg-green-500 rounded-full flex items-center justify-center mr-3">
                  <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                  </svg>
                </div>
                <div>
                  <h3 className="font-semibold text-green-800 text-lg">WhatsApp Notifications</h3>
                  <p className="text-sm text-green-600">Get alerts when ONUs go offline or come back online</p>
                </div>
              </div>
              {/* Toggle Switch */}
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={formData.whatsapp_enabled}
                  onChange={(e) => setFormData({ ...formData, whatsapp_enabled: e.target.checked })}
                />
                <div className="w-14 h-7 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-green-500"></div>
                <span className="ml-3 text-sm font-medium text-gray-700">{formData.whatsapp_enabled ? 'ON' : 'OFF'}</span>
              </label>
            </div>

            {/* API Configuration - Always visible */}
            <div className={`space-y-4 p-4 rounded-xl border ${formData.whatsapp_enabled ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-100'}`}>
              <h4 className="font-medium text-gray-700 flex items-center">
                <svg className="w-5 h-5 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                API Configuration
              </h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">API URL</label>
                  <input
                    type="url"
                    className={`w-full rounded-lg border shadow-sm border-gray-300 p-3 focus:ring-2 focus:ring-green-500 focus:border-green-500 ${!formData.whatsapp_enabled ? 'bg-gray-100 text-gray-500' : ''}`}
                    value={formData.whatsapp_api_url}
                    onChange={(e) => setFormData({ ...formData, whatsapp_api_url: e.target.value })}
                    placeholder="https://proxsms.com/api/send/whatsapp"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Secret Key</label>
                  <input
                    type="password"
                    className={`w-full rounded-lg border shadow-sm border-gray-300 p-3 focus:ring-2 focus:ring-green-500 focus:border-green-500 ${!formData.whatsapp_enabled ? 'bg-gray-100 text-gray-500' : ''}`}
                    value={formData.whatsapp_secret}
                    onChange={(e) => setFormData({ ...formData, whatsapp_secret: e.target.value })}
                    placeholder="Your ProxSMS secret key"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Device ID (Account)</label>
                <input
                  type="text"
                  className={`w-full rounded-lg border shadow-sm border-gray-300 p-3 focus:ring-2 focus:ring-green-500 focus:border-green-500 ${!formData.whatsapp_enabled ? 'bg-gray-100 text-gray-500' : ''}`}
                  value={formData.whatsapp_account}
                  onChange={(e) => setFormData({ ...formData, whatsapp_account: e.target.value })}
                  placeholder="Your WhatsApp device ID"
                />
              </div>
            </div>

            {/* Recipients Management */}
            <div className={`space-y-4 p-4 rounded-xl border ${formData.whatsapp_enabled ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-100'}`}>
              <h4 className="font-medium text-gray-700 flex items-center">
                <svg className="w-5 h-5 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                Recipients ({formData.whatsapp_recipients.length})
              </h4>

              {/* Add New Recipient */}
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  type="text"
                  placeholder="Name"
                  className={`flex-1 rounded-lg border shadow-sm border-gray-300 p-2.5 text-sm focus:ring-2 focus:ring-green-500 ${!formData.whatsapp_enabled ? 'bg-gray-100 text-gray-500' : ''}`}
                  value={newRecipient.name}
                  onChange={(e) => setNewRecipient({ ...newRecipient, name: e.target.value })}
                />
                <input
                  type="tel"
                  placeholder="Phone (+961...)"
                  className={`flex-1 rounded-lg border shadow-sm border-gray-300 p-2.5 text-sm focus:ring-2 focus:ring-green-500 ${!formData.whatsapp_enabled ? 'bg-gray-100 text-gray-500' : ''}`}
                  value={newRecipient.phone}
                  onChange={(e) => setNewRecipient({ ...newRecipient, phone: e.target.value })}
                />
                <button
                  type="button"
                  onClick={addRecipient}
                  disabled={!formData.whatsapp_enabled}
                  className="px-4 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1 text-sm font-medium"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add
                </button>
              </div>

              {/* Recipients List */}
              {formData.whatsapp_recipients.length > 0 ? (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {formData.whatsapp_recipients.map((recipient, index) => (
                    <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100 group hover:bg-gray-100 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-green-100 text-green-600 rounded-full flex items-center justify-center font-semibold text-sm">
                          {recipient.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-gray-800 text-sm">{recipient.name}</p>
                          <p className="text-xs text-gray-500">{recipient.phone}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => handleTestWhatsApp(recipient.phone, recipient.name, index)}
                          disabled={testingRecipient !== null || !formData.whatsapp_enabled}
                          className="p-1.5 text-green-600 hover:bg-green-100 rounded-lg transition-colors disabled:opacity-50"
                          title="Send test message"
                        >
                          {testingRecipient === index ? (
                            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                            </svg>
                          ) : (
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                            </svg>
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={() => removeRecipient(index)}
                          className="p-1.5 text-red-600 hover:bg-red-100 rounded-lg transition-colors"
                          title="Remove recipient"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-gray-400">
                  <svg className="w-10 h-10 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <p className="text-sm">No recipients added yet</p>
                  <p className="text-xs">Add recipients to receive notifications</p>
                </div>
              )}
            </div>

            {/* Info Box */}
            <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
              <div className="flex items-start">
                <svg className="w-5 h-5 text-blue-500 mt-0.5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <div>
                  <p className="text-sm font-medium text-blue-800">When enabled, you'll receive notifications for:</p>
                  <ul className="text-sm text-blue-700 mt-1 ml-4 list-disc">
                    <li>ONU goes offline</li>
                    <li>ONU comes back online</li>
                    <li>OLT connection issues</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* SNMP Trap Settings */}
            <div className="mt-6 p-4 bg-gradient-to-br from-purple-50 to-indigo-50 rounded-2xl border border-purple-100">
              <h3 className="text-lg font-semibold text-purple-900 mb-4 flex items-center">
                <svg className="w-6 h-6 mr-2 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                SNMP Trap Receiver (Instant Alerts)
              </h3>

              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-sm font-medium text-gray-700">Enable Trap Receiver</p>
                  <p className="text-xs text-gray-500">Receive instant ONU status changes from OLT</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={formData.trap_enabled}
                    onChange={(e) => setFormData({ ...formData, trap_enabled: e.target.checked })}
                  />
                  <div className="w-14 h-7 bg-gray-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-purple-500"></div>
                  <span className="ml-3 text-sm font-medium text-gray-700">{formData.trap_enabled ? 'ON' : 'OFF'}</span>
                </label>
              </div>

              <div className={`space-y-4 p-4 rounded-xl border ${formData.trap_enabled ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-100'}`}>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Trap Port</label>
                  <input
                    type="number"
                    className={`w-full rounded-lg border shadow-sm border-gray-300 p-3 focus:ring-2 focus:ring-purple-500 focus:border-purple-500 ${!formData.trap_enabled ? 'bg-gray-100 text-gray-500' : ''}`}
                    value={formData.trap_port}
                    onChange={(e) => setFormData({ ...formData, trap_port: e.target.value })}
                    placeholder="162"
                  />
                  <p className="text-xs text-gray-500 mt-1">Default: 162 (requires root). Use 1620+ if not running as root.</p>
                </div>
              </div>

              <div className="p-3 bg-purple-100 rounded-xl border border-purple-200 mt-4">
                <div className="flex items-start">
                  <svg className="w-5 h-5 text-purple-600 mt-0.5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <p className="text-sm font-medium text-purple-800">Configure your OLT:</p>
                    <ul className="text-sm text-purple-700 mt-1 ml-4 list-disc">
                      <li>Trap Server IP: 172.22.22.20</li>
                      <li>Trap Port: {formData.trap_port || 162}</li>
                      <li>Community: public</li>
                    </ul>
                    <p className="text-xs text-purple-600 mt-2">Traps provide instant alerts vs polling (60s delay)</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 flex justify-end">
            <button type="submit" disabled={loading} className="px-6 py-3 bg-green-600 text-white rounded-xl hover:bg-green-700 disabled:opacity-50 font-medium transition-colors">
              {loading ? 'Saving...' : 'Save WhatsApp Settings'}
            </button>
          </div>
        </form>
      )}

      {activeTab === 'password' && (
        <form onSubmit={handlePasswordChange}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Current Password</label>
              <input
                type="password"
                required
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
                value={passwordData.current_password}
                onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
              <input
                type="password"
                required
                minLength="6"
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
                value={passwordData.new_password}
                onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirm New Password</label>
              <input
                type="password"
                required
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500"
                value={passwordData.confirm_password}
                onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
              />
            </div>
          </div>
          <div className="mt-6 flex justify-end">
            <button type="submit" disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
              {loading ? 'Changing...' : 'Change Password'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

// Traffic Graph Modal - Historical Traffic Charts
function TrafficGraphModal({ isOpen, onClose, entityType, entityId, entityName, token }) {
  const [timeRange, setTimeRange] = useState('1h');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [tooltip, setTooltip] = useState(null);
  const canvasRef = useRef(null);
  const chartRef = useRef(null);
  const containerRef = useRef(null);

  const timeRanges = [
    { key: '5m', label: '5 Min' },
    { key: '15m', label: '15 Min' },
    { key: '30m', label: '30 Min' },
    { key: '1h', label: '1 Hour' },
    { key: '6h', label: '6 Hours' },
    { key: '24h', label: '24 Hours' },
    { key: '1w', label: '1 Week' },
    { key: '1M', label: '1 Month' },
  ];

  // Format bandwidth with auto units
  const formatBandwidth = (kbps, decimals = 1) => {
    if (kbps >= 1000000) return `${(kbps / 1000000).toFixed(decimals)} Gbps`;
    if (kbps >= 1000) return `${(kbps / 1000).toFixed(decimals)} Mbps`;
    return `${kbps.toFixed(0)} Kbps`;
  };

  const fetchData = useCallback(async () => {
    if (!isOpen || !entityId) return;

    setLoading(true);
    setError(null);

    try {
      let url;
      if (entityType === 'onu') {
        url = `/api/traffic/history/onu/${entityId}?range=${timeRange}`;
      } else if (entityType === 'pon') {
        const [oltId, ponPort] = entityId.split(':');
        url = `/api/traffic/history/pon/${oltId}/${ponPort}?range=${timeRange}`;
      } else if (entityType === 'olt') {
        url = `/api/traffic/history/olt/${entityId}?range=${timeRange}`;
      }

      const response = await api.get(url);
      setData(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load traffic data');
    } finally {
      setLoading(false);
    }
  }, [isOpen, entityId, entityType, timeRange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Draw chart when data changes
  useEffect(() => {
    if (!data || !data.data || data.data.length === 0 || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    // Clear previous chart
    if (chartRef.current) {
      chartRef.current = null;
    }

    // Set canvas size with device pixel ratio for crisp rendering
    const container = canvas.parentElement;
    const dpr = window.devicePixelRatio || 1;
    const displayWidth = container.clientWidth;
    const displayHeight = 320;
    canvas.width = displayWidth * dpr;
    canvas.height = displayHeight * dpr;
    canvas.style.width = displayWidth + 'px';
    canvas.style.height = displayHeight + 'px';
    ctx.scale(dpr, dpr);

    const width = displayWidth;
    const height = displayHeight;
    const padding = { top: 50, right: 30, bottom: 50, left: 70 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Clear canvas with dark background
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, width, height);

    // Get data points
    const points = data.data;
    const rxValues = points.map(p => p.rx_kbps);
    const txValues = points.map(p => p.tx_kbps);
    const allValues = [...rxValues, ...txValues];
    const maxValue = Math.max(...allValues, 100);

    // Nice round numbers for Y axis
    const magnitude = Math.pow(10, Math.floor(Math.log10(maxValue)));
    const niceMax = Math.ceil(maxValue / magnitude) * magnitude * 1.1;

    // Draw minor grid lines
    ctx.strokeStyle = 'rgba(71, 85, 105, 0.3)';
    ctx.lineWidth = 0.5;
    const minorGridLines = 10;
    for (let i = 0; i <= minorGridLines; i++) {
      const y = padding.top + (chartHeight / minorGridLines) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
    }

    // Draw major grid lines and Y-axis labels
    ctx.strokeStyle = 'rgba(100, 116, 139, 0.5)';
    ctx.lineWidth = 1;
    const majorGridLines = 5;
    for (let i = 0; i <= majorGridLines; i++) {
      const y = padding.top + (chartHeight / majorGridLines) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      // Y-axis labels
      const value = niceMax - (niceMax / majorGridLines) * i;
      ctx.fillStyle = '#94a3b8';
      ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';
      ctx.fillText(formatBandwidth(value, 0), padding.left - 10, y);
    }

    // Draw vertical grid lines
    const verticalLines = Math.min(8, points.length);
    for (let i = 0; i <= verticalLines; i++) {
      const x = padding.left + (chartWidth / verticalLines) * i;
      ctx.strokeStyle = 'rgba(71, 85, 105, 0.3)';
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(x, padding.top);
      ctx.lineTo(x, padding.top + chartHeight);
      ctx.stroke();
    }

    // Draw X-axis labels (timestamps)
    const labelCount = Math.min(6, points.length);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    if (labelCount > 0 && points.length > 0) {
      for (let i = 0; i < labelCount; i++) {
        const idx = labelCount === 1 ? 0 : Math.floor((points.length - 1) * i / (labelCount - 1));
        if (idx >= 0 && idx < points.length && points[idx]) {
          const x = points.length === 1 ? padding.left + chartWidth / 2 : padding.left + (chartWidth * idx / (points.length - 1));
          const time = new Date(points[idx].timestamp);
          let label;
          if (timeRange === '1w' || timeRange === '1M') {
            label = time.toLocaleDateString('en', { month: 'short', day: 'numeric' });
          } else if (timeRange === '24h' || timeRange === '6h') {
            label = time.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' });
          } else {
            label = time.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
          }
          ctx.fillText(label, x, height - padding.bottom + 10);
        }
      }
    }

    // Draw chart border
    ctx.strokeStyle = 'rgba(100, 116, 139, 0.5)';
    ctx.lineWidth = 1;
    ctx.strokeRect(padding.left, padding.top, chartWidth, chartHeight);

    // Helper function to draw smooth bezier curve with gradient fill
    const drawSmoothLine = (values, strokeColor, gradientColors) => {
      if (values.length === 0) return;

      const getX = (i) => padding.left + (chartWidth * i / Math.max(values.length - 1, 1));
      const getY = (val) => padding.top + chartHeight - (val / niceMax * chartHeight);

      // Create gradient
      const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartHeight);
      gradient.addColorStop(0, gradientColors[0]);
      gradient.addColorStop(1, gradientColors[1]);

      // Single point - draw a glowing dot
      if (values.length === 1) {
        const x = padding.left + chartWidth / 2;
        const y = getY(values[0]);

        // Glow effect
        ctx.beginPath();
        ctx.fillStyle = gradientColors[0];
        ctx.arc(x, y, 8, 0, Math.PI * 2);
        ctx.fill();

        ctx.beginPath();
        ctx.fillStyle = strokeColor;
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();
        return;
      }

      // Draw filled area first
      ctx.beginPath();
      ctx.moveTo(getX(0), getY(values[0]));

      // Use bezier curves for smoothness
      for (let i = 1; i < values.length; i++) {
        const x0 = getX(i - 1);
        const y0 = getY(values[i - 1]);
        const x1 = getX(i);
        const y1 = getY(values[i]);
        const cpx = (x0 + x1) / 2;
        ctx.bezierCurveTo(cpx, y0, cpx, y1, x1, y1);
      }

      ctx.lineTo(getX(values.length - 1), padding.top + chartHeight);
      ctx.lineTo(getX(0), padding.top + chartHeight);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();

      // Draw line on top
      ctx.beginPath();
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 2.5;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      ctx.moveTo(getX(0), getY(values[0]));
      for (let i = 1; i < values.length; i++) {
        const x0 = getX(i - 1);
        const y0 = getY(values[i - 1]);
        const x1 = getX(i);
        const y1 = getY(values[i]);
        const cpx = (x0 + x1) / 2;
        ctx.bezierCurveTo(cpx, y0, cpx, y1, x1, y1);
      }
      ctx.stroke();

      // Draw dots at data points for short time ranges
      if (values.length <= 30) {
        values.forEach((val, i) => {
          ctx.beginPath();
          ctx.fillStyle = '#0f172a';
          ctx.arc(getX(i), getY(val), 4, 0, Math.PI * 2);
          ctx.fill();
          ctx.beginPath();
          ctx.fillStyle = strokeColor;
          ctx.arc(getX(i), getY(val), 2.5, 0, Math.PI * 2);
          ctx.fill();
        });
      }
    };

    // Draw Download (TX from OLT = to customer) - Green
    drawSmoothLine(txValues, '#22c55e', ['rgba(34, 197, 94, 0.4)', 'rgba(34, 197, 94, 0.02)']);

    // Draw Upload (RX at OLT = from customer) - Cyan/Blue
    drawSmoothLine(rxValues, '#06b6d4', ['rgba(6, 182, 212, 0.35)', 'rgba(6, 182, 212, 0.02)']);

    // Draw legend box
    const legendX = padding.left + 10;
    const legendY = 12;

    ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
    ctx.strokeStyle = 'rgba(100, 116, 139, 0.3)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(legendX, legendY, 200, 28, 6);
    ctx.fill();
    ctx.stroke();

    // Download legend
    ctx.fillStyle = '#22c55e';
    ctx.beginPath();
    ctx.arc(legendX + 15, legendY + 14, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#e2e8f0';
    ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText('Download', legendX + 26, legendY + 14);

    // Upload legend
    ctx.fillStyle = '#06b6d4';
    ctx.beginPath();
    ctx.arc(legendX + 110, legendY + 14, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#e2e8f0';
    ctx.fillText('Upload', legendX + 121, legendY + 14);

    // Store chart info for mouse interaction
    chartRef.current = {
      points,
      padding,
      chartWidth,
      chartHeight,
      niceMax,
      getX: (i) => padding.left + (chartWidth * i / Math.max(points.length - 1, 1)),
      getY: (val) => padding.top + chartHeight - (val / niceMax * chartHeight)
    };
  }, [data, timeRange]);

  // Mouse move handler for tooltip
  const handleMouseMove = useCallback((e) => {
    if (!chartRef.current || !data || !data.data || data.data.length === 0) {
      setTooltip(null);
      return;
    }

    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const { points, padding, chartWidth, chartHeight } = chartRef.current;

    // Check if mouse is in chart area
    if (x < padding.left || x > padding.left + chartWidth || y < padding.top || y > padding.top + chartHeight) {
      setTooltip(null);
      return;
    }

    // Find closest data point
    const relX = x - padding.left;
    const idx = Math.round((relX / chartWidth) * (points.length - 1));

    if (idx >= 0 && idx < points.length) {
      const point = points[idx];
      const tooltipX = chartRef.current.getX(idx);
      setTooltip({
        x: tooltipX,
        y: y,
        data: point,
        visible: true
      });
    }
  }, [data]);

  const handleMouseLeave = useCallback(() => {
    setTooltip(null);
  }, []);

  if (!isOpen) return null;

  // Calculate stats
  const stats = data && data.data && data.data.length > 0 ? {
    maxDownload: Math.max(...data.data.map(d => d.tx_kbps)),
    maxUpload: Math.max(...data.data.map(d => d.rx_kbps)),
    avgDownload: data.data.reduce((sum, d) => sum + d.tx_kbps, 0) / data.data.length,
    avgUpload: data.data.reduce((sum, d) => sum + d.rx_kbps, 0) / data.data.length,
    // Total data transferred (approximate based on samples)
    totalDownload: data.data.reduce((sum, d) => sum + d.tx_kbps, 0) * 60 / 8 / 1024, // MB (assuming 60s intervals)
    totalUpload: data.data.reduce((sum, d) => sum + d.rx_kbps, 0) * 60 / 8 / 1024, // MB
  } : null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Traffic Monitor - ${entityName}`} size="xl">
      <div className="space-y-4">
        {/* Time Range Selector - Modern pill style */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex gap-1 bg-slate-800 p-1 rounded-xl">
            {timeRanges.map(range => (
              <button
                key={range.key}
                onClick={() => setTimeRange(range.key)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all duration-200 ${
                  timeRange === range.key
                    ? 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white shadow-lg shadow-blue-500/25'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700'
                }`}
              >
                {range.label}
              </button>
            ))}
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-white bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors flex items-center gap-2"
          >
            <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>

        {/* Chart Area - Dark theme */}
        <div
          ref={containerRef}
          className="bg-slate-900 rounded-xl border border-slate-700 overflow-hidden relative"
          style={{ minHeight: '360px' }}
        >
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm z-10">
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 border-4 border-slate-600 border-t-cyan-500 rounded-full animate-spin"></div>
                <span className="text-slate-400 text-sm font-medium">Loading traffic data...</span>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center h-[320px]">
              <div className="text-center">
                <div className="w-14 h-14 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
                  <svg className="w-7 h-7 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <p className="text-red-400 font-medium">{error}</p>
              </div>
            </div>
          )}

          {!loading && !error && data && data.data.length === 0 && (
            <div className="flex items-center justify-center h-[320px]">
              <div className="text-center">
                <div className="w-14 h-14 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-3">
                  <svg className="w-7 h-7 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <p className="text-slate-300 font-medium">No data available for this period</p>
                <p className="text-slate-500 text-sm mt-1">Data will appear after traffic is collected</p>
              </div>
            </div>
          )}

          {!error && data && data.data.length > 0 && (
            <div className="p-4">
              <canvas
                ref={canvasRef}
                className="w-full cursor-crosshair"
                onMouseMove={handleMouseMove}
                onMouseLeave={handleMouseLeave}
              ></canvas>

              {/* Tooltip */}
              {tooltip && tooltip.visible && (
                <div
                  className="absolute pointer-events-none z-20 bg-slate-800 border border-slate-600 rounded-lg shadow-xl p-3 text-sm"
                  style={{
                    left: Math.min(tooltip.x, containerRef.current?.clientWidth - 180) + 'px',
                    top: '60px',
                    transform: 'translateX(-50%)'
                  }}
                >
                  <div className="text-slate-400 text-xs mb-2 font-medium">
                    {new Date(tooltip.data.timestamp).toLocaleString()}
                  </div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="w-2 h-2 rounded-full bg-green-500"></span>
                    <span className="text-slate-300">Download:</span>
                    <span className="text-green-400 font-bold">{formatBandwidth(tooltip.data.tx_kbps)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-cyan-500"></span>
                    <span className="text-slate-300">Upload:</span>
                    <span className="text-cyan-400 font-bold">{formatBandwidth(tooltip.data.rx_kbps)}</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Stats Summary - Professional cards */}
        {!loading && stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-gradient-to-br from-green-500/10 to-green-600/5 border border-green-500/20 rounded-xl p-3">
              <p className="text-xs text-green-400 font-medium flex items-center gap-1">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" transform="rotate(180 10 10)"/></svg>
                Peak Download
              </p>
              <p className="text-xl font-bold text-green-300 mt-1">{formatBandwidth(stats.maxDownload)}</p>
            </div>
            <div className="bg-gradient-to-br from-cyan-500/10 to-cyan-600/5 border border-cyan-500/20 rounded-xl p-3">
              <p className="text-xs text-cyan-400 font-medium flex items-center gap-1">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd"/></svg>
                Peak Upload
              </p>
              <p className="text-xl font-bold text-cyan-300 mt-1">{formatBandwidth(stats.maxUpload)}</p>
            </div>
            <div className="bg-gradient-to-br from-slate-500/10 to-slate-600/5 border border-slate-500/20 rounded-xl p-3">
              <p className="text-xs text-slate-400 font-medium">Avg Download</p>
              <p className="text-xl font-bold text-green-300 mt-1">{formatBandwidth(stats.avgDownload)}</p>
            </div>
            <div className="bg-gradient-to-br from-slate-500/10 to-slate-600/5 border border-slate-500/20 rounded-xl p-3">
              <p className="text-xs text-slate-400 font-medium">Avg Upload</p>
              <p className="text-xl font-bold text-cyan-300 mt-1">{formatBandwidth(stats.avgUpload)}</p>
            </div>
          </div>
        )}

        {/* Data Points Info */}
        {data && (
          <div className="flex items-center justify-center gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
              </svg>
              {data.data_points} samples
            </span>
            <span>•</span>
            <span>{data.start_time ? new Date(data.start_time).toLocaleString() : ''}</span>
            <span>→</span>
            <span>{data.end_time ? new Date(data.end_time).toLocaleString() : ''}</span>
          </div>
        )}
      </div>
    </Modal>
  );
}

// OLT Card Component - Enterprise Pro Design
function OLTCard({ olt, onSelect, onPoll, onDelete, isSelected, isAdmin, onGraph }) {
  const [polling, setPolling] = useState(false);

  const handlePoll = async (e) => {
    e.stopPropagation();
    setPolling(true);
    try {
      await onPoll(olt.id);
    } finally {
      setPolling(false);
    }
  };

  const handleDelete = async (e) => {
    e.stopPropagation();
    if (window.confirm(`Delete OLT "${olt.name}" and all its ONUs?`)) {
      await onDelete(olt.id);
    }
  };

  const onlinePercent = olt.onu_count > 0 ? Math.round((olt.online_onu_count / olt.onu_count) * 100) : 0;

  return (
    <div
      onClick={() => onSelect(olt.id)}
      className={`bg-white rounded-xl border cursor-pointer transition-all duration-200 hover:shadow-sm overflow-hidden ${
        isSelected ? 'ring-2 ring-[#2563eb] border-blue-200' : 'border-[#e8eaed]'
      }`}
    >
      {/* Header */}
      <div className="p-4 border-b border-[#e8eaed]">
        <div className="flex justify-between items-start">
          <div className="flex items-start gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${olt.is_online ? 'bg-blue-50' : 'bg-gray-100'}`}>
              <svg className={`w-5 h-5 ${olt.is_online ? 'text-[#2563eb]' : 'text-[#9ca3af]'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-[#111827]">{olt.name}</h3>
              <p className="text-sm text-[#9ca3af] font-mono">{olt.ip_address}</p>
            </div>
          </div>
          <StatusBadge online={olt.is_online} />
        </div>
      </div>

      {/* Body */}
      <div className="p-4">
        {olt.model && <p className="text-xs text-[#9ca3af] mb-3">{olt.model}</p>}

        {/* Stats with progress bar */}
        <div className="mb-3">
          <div className="flex justify-between text-sm mb-1.5">
            <span className="text-[#4b5563]">ONUs Online</span>
            <span className="font-medium text-[#111827]">{olt.online_onu_count} / {olt.onu_count}</span>
          </div>
          <div className="h-2 bg-[#f4f5f7] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${onlinePercent > 80 ? 'bg-[#059669]' : onlinePercent > 50 ? 'bg-amber-500' : 'bg-[#dc2626]'}`}
              style={{ width: `${onlinePercent}%` }}
            ></div>
          </div>
        </div>

        {olt.last_poll && (
          <p className="text-xs text-[#9ca3af] flex items-center gap-1.5 mb-2">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Last poll: {new Date(olt.last_poll).toLocaleString()}
          </p>
        )}
        {olt.last_error && (
          <p className="text-xs text-[#dc2626] truncate flex items-center gap-1.5" title={olt.last_error}>
            <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            {olt.last_error}
          </p>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 bg-[#fafbfc] border-t border-[#e8eaed] flex justify-end gap-2">
        <button
          onClick={(e) => { e.stopPropagation(); onGraph && onGraph('olt', olt.id, olt.name); }}
          className="px-3 py-1.5 text-sm text-purple-600 border border-[#e8eaed] bg-white rounded-lg hover:bg-purple-50 font-medium transition-all duration-150 flex items-center gap-1.5"
          title="View traffic graph"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          Graph
        </button>
        <button
          onClick={handlePoll}
          disabled={polling}
          className="px-3 py-1.5 text-sm bg-[#2563eb] text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium transition-all duration-150 flex items-center gap-1.5"
        >
          {polling ? (
            <>
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Polling...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Poll
            </>
          )}
        </button>
        {isAdmin && (
          <button
            onClick={handleDelete}
            className="px-3 py-1.5 text-sm text-[#dc2626] border border-[#e8eaed] bg-white rounded-lg hover:bg-red-50 font-medium transition-all duration-150"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  );
}

// ONU Table Component - Enterprise Pro Design
function ONUTable({ onus, onEdit, onDelete, isAdmin, trafficData, onGraph }) {
  const [previewImages, setPreviewImages] = useState(null);
  const [previewTitle, setPreviewTitle] = useState('');

  // Create a map of MAC -> traffic for quick lookup
  const trafficMap = {};
  if (trafficData && trafficData.traffic) {
    trafficData.traffic.forEach(t => {
      trafficMap[t.mac_address] = t;
    });
  }

  const openPreview = (onu) => {
    const images = onu.image_urls || (onu.image_url ? [onu.image_url] : []);
    if (images.length > 0) {
      setPreviewImages(images);
      setPreviewTitle(onu.description || `ONU ${onu.pon_port}:${onu.onu_id}`);
    }
  };

  if (onus.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-[#e8eaed] p-12 text-center">
        <div className="w-14 h-14 bg-[#f4f5f7] rounded-lg flex items-center justify-center mx-auto mb-4">
          <svg className="w-7 h-7 text-[#9ca3af]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
          </svg>
        </div>
        <p className="text-[#111827] font-medium">No ONUs found</p>
        <p className="text-[#9ca3af] text-sm mt-1">Try adjusting your filters or search query</p>
      </div>
    );
  }

  return (
    <>
      <ImagePreviewModal
        isOpen={!!previewImages}
        onClose={() => setPreviewImages(null)}
        images={previewImages || []}
        title={previewTitle}
      />
      <div className="bg-white rounded-xl border border-[#e8eaed] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="bg-[#f4f5f7] border-b border-[#e8eaed]">
                <th className="px-4 py-3 text-left text-xs font-semibold text-[#4b5563] uppercase tracking-wider">OLT</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-[#4b5563] uppercase tracking-wider">PON/ONU</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-[#4b5563] uppercase tracking-wider">MAC Address</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-[#4b5563] uppercase tracking-wider">Customer</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-[#4b5563] uppercase tracking-wider">Traffic</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-[#4b5563] uppercase tracking-wider">Photo</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-[#4b5563] uppercase tracking-wider">Distance</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-[#4b5563] uppercase tracking-wider">RX Power</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-[#4b5563] uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-[#4b5563] uppercase tracking-wider">Last Seen</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-[#4b5563] uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e8eaed]">
              {onus.map((onu) => {
                const images = onu.image_urls || (onu.image_url ? [onu.image_url] : []);
                const hasImages = images.length > 0;
                return (
                  <tr key={onu.id} className="hover:bg-blue-50/50 transition-colors duration-150 group">
                    <td className="px-5 py-4 whitespace-nowrap">
                      <span className="text-sm font-semibold text-gray-800">{onu.olt_name}</span>
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-1 bg-gray-100 text-gray-700 text-sm font-mono rounded-lg">
                        0/{onu.pon_port}:{onu.onu_id}
                      </span>
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      <span className="text-sm font-mono text-gray-600 bg-gray-50 px-2 py-1 rounded">{onu.mac_address}</span>
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <div>
                          <span className="text-sm font-medium text-gray-800">{onu.description || <span className="text-gray-400 italic">No name</span>}</span>
                          {onu.region_name && (
                            <p className="text-xs font-medium" style={{ color: onu.region_color || '#6366F1' }}>{onu.region_name}</p>
                          )}
                        </div>
                        {onu.latitude && onu.longitude && (
                          <button
                            onClick={() => window.open(`https://www.google.com/maps?q=${onu.latitude},${onu.longitude}`, '_blank')}
                            className="p-1 text-emerald-500 hover:text-emerald-700 hover:bg-emerald-50 rounded-lg transition-colors"
                            title="View on map"
                            aria-label="View on map"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap text-center">
                      <div className="flex items-center justify-center gap-2">
                        {(() => {
                          const traffic = trafficMap[onu.mac_address];
                          if (!traffic) {
                            return <span className="text-gray-400 text-xs">-</span>;
                          }
                          const rx = traffic.rx_kbps || 0;
                          const tx = traffic.tx_kbps || 0;
                          return (
                            <div className="flex flex-col items-center gap-0.5">
                              <span className={`text-xs font-semibold flex items-center gap-1 ${rx > 10000 ? 'text-green-600' : rx > 1000 ? 'text-blue-600' : 'text-gray-600'}`}>
                                <svg className="w-3 h-3 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                                </svg>
                                {rx > 1000 ? `${(rx/1000).toFixed(1)}M` : `${rx.toFixed(0)}K`}
                              </span>
                              <span className={`text-xs font-semibold flex items-center gap-1 ${tx > 10000 ? 'text-blue-600' : tx > 1000 ? 'text-indigo-600' : 'text-gray-600'}`}>
                                <svg className="w-3 h-3 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                                </svg>
                                {tx > 1000 ? `${(tx/1000).toFixed(1)}M` : `${tx.toFixed(0)}K`}
                              </span>
                            </div>
                          );
                        })()}
                        {/* Graph Button */}
                        <button
                          onClick={() => onGraph && onGraph('onu', onu.id, onu.description || `ONU ${onu.pon_port}:${onu.onu_id}`)}
                          className="p-1.5 text-purple-500 hover:text-purple-700 hover:bg-purple-50 rounded-lg transition-colors"
                          title="View traffic graph"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                          </svg>
                        </button>
                      </div>
                    </td>
                    <td className="px-3 py-4 whitespace-nowrap text-center">
                      {hasImages ? (
                        <button
                          onClick={() => openPreview(onu)}
                          className="relative inline-block group"
                          title={`View ${images.length} photo${images.length > 1 ? 's' : ''}`}
                          aria-label={`View ${images.length} photo${images.length > 1 ? 's' : ''}`}
                        >
                          <img
                            src={images[0]}
                            alt="ONU"
                            className="w-10 h-10 rounded-lg object-cover border-2 border-gray-200 hover:border-blue-500 transition cursor-pointer"
                          />
                          {images.length > 1 && (
                            <span className="absolute -top-1 -right-1 bg-blue-500 text-white text-xs w-5 h-5 rounded-full flex items-center justify-center">
                              {images.length}
                            </span>
                          )}
                        </button>
                      ) : (
                        <span className="text-gray-300">
                          <svg className="w-6 h-6 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      {onu.distance ? (
                        <span className="inline-flex items-center px-2.5 py-1 bg-blue-50 text-blue-700 text-sm font-medium rounded-lg">
                          {onu.distance}m
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      {onu.rx_power ? (
                        <span className={`inline-flex items-center px-2.5 py-1 text-sm font-semibold rounded-lg ${
                          !onu.is_online ? 'bg-gray-100 text-gray-400 italic' :
                          onu.rx_power < -25 ? 'bg-red-50 text-red-700' :
                          onu.rx_power < -20 ? 'bg-amber-50 text-amber-700' :
                          'bg-emerald-50 text-emerald-700'
                        }`} title={!onu.is_online ? 'Last known value (ONU offline)' : ''}>
                          {onu.rx_power.toFixed(2)} dBm{!onu.is_online && ' *'}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      <StatusBadge online={onu.is_online} />
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      <span className="text-sm text-gray-500">{new Date(onu.last_seen).toLocaleString()}</span>
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => onEdit(onu)}
                          className="px-3 py-1.5 text-sm font-medium text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition-colors"
                        >
                          Edit
                        </button>
                        {isAdmin && (
                          <button
                            onClick={() => {
                              if (window.confirm('Delete this ONU record?')) {
                                onDelete(onu.id);
                              }
                            }}
                            className="px-3 py-1.5 text-sm font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded-lg transition-colors"
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// Mobile ONU Card - Premium Material Design
function ONUCard({ onu, onEdit, onDelete, isAdmin, onImagePreview }) {
  const images = onu.image_urls || (onu.image_url ? [onu.image_url] : []);
  const hasImages = images.length > 0;

  return (
    <div className="bg-white rounded-2xl shadow-material-1 p-4 mb-4 border border-gray-100 relative overflow-hidden">
      {/* Status indicator bar */}
      <div className={`absolute top-0 left-0 right-0 h-1 ${onu.is_online ? 'bg-gradient-to-r from-emerald-400 to-emerald-500' : 'bg-gradient-to-r from-red-400 to-red-500'}`}></div>

      <div className="flex justify-between items-start mb-3 pt-1">
        <div className="flex items-start gap-3">
          {/* Image thumbnail */}
          {hasImages ? (
            <button
              onClick={() => onImagePreview(onu)}
              className="relative flex-shrink-0"
              title={`View ${images.length} photo${images.length > 1 ? 's' : ''}`}
              aria-label={`View ${images.length} photo${images.length > 1 ? 's' : ''}`}
            >
              <img
                src={images[0]}
                alt="ONU"
                className="w-14 h-14 rounded-xl object-cover border-2 border-gray-200 shadow-sm"
              />
              {images.length > 1 && (
                <span className="absolute -top-1 -right-1 bg-primary-500 text-white text-xs w-5 h-5 rounded-full flex items-center justify-center shadow-sm">
                  {images.length}
                </span>
              )}
            </button>
          ) : (
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-gray-100 to-gray-50 flex items-center justify-center flex-shrink-0 shadow-sm">
              <svg className="w-6 h-6 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
          )}
          <div>
            <p className="font-bold text-gray-800">{onu.description || 'No Name'}</p>
            {onu.region_name && (
              <p className="text-xs font-semibold" style={{ color: onu.region_color || '#6366F1' }}>{onu.region_name}</p>
            )}
            <p className="text-xs text-gray-500 font-mono bg-gray-50 px-1.5 py-0.5 rounded mt-1 inline-block">{onu.mac_address}</p>
          </div>
        </div>
        <StatusBadge online={onu.is_online} />
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm mb-3">
        <div className="bg-gradient-to-br from-slate-50 to-slate-100 rounded-xl p-2.5 border border-slate-200/50">
          <span className="text-slate-500 text-xs">OLT</span>
          <p className="font-semibold text-slate-700">{onu.olt_name}</p>
        </div>
        <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 rounded-xl p-2.5 border border-indigo-200/50">
          <span className="text-indigo-500 text-xs">Port</span>
          <p className="font-semibold font-mono text-indigo-700">0/{onu.pon_port}:{onu.onu_id}</p>
        </div>
        <div className="bg-gradient-to-br from-cyan-50 to-cyan-100 rounded-xl p-2.5 border border-cyan-200/50">
          <span className="text-cyan-500 text-xs">Distance</span>
          <p className="font-semibold text-cyan-700">{onu.distance ? `${onu.distance}m` : '-'}</p>
        </div>
        <div className={`rounded-xl p-2.5 border ${onu.rx_power ? (!onu.is_online ? 'bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200/50' : onu.rx_power < -25 ? 'bg-gradient-to-br from-red-50 to-red-100 border-red-200/50' : onu.rx_power < -20 ? 'bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200/50' : 'bg-gradient-to-br from-emerald-50 to-emerald-100 border-emerald-200/50') : 'bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200/50'}`}>
          <span className={`text-xs ${onu.rx_power ? (!onu.is_online ? 'text-gray-400' : onu.rx_power < -25 ? 'text-red-500' : onu.rx_power < -20 ? 'text-amber-500' : 'text-emerald-500') : 'text-gray-400'}`}>RX Power</span>
          <p className={`font-semibold ${onu.rx_power ? (!onu.is_online ? 'text-gray-400 italic' : onu.rx_power < -25 ? 'text-red-700' : onu.rx_power < -20 ? 'text-amber-700' : 'text-emerald-700') : 'text-gray-400'}`} title={onu.rx_power && !onu.is_online ? 'Last known value (ONU offline)' : ''}>
            {onu.rx_power ? `${onu.rx_power.toFixed(2)} dBm${!onu.is_online ? ' *' : ''}` : '-'}
          </p>
        </div>
      </div>
      <div className="flex justify-between items-center pt-2 border-t border-gray-100">
        <p className="text-xs text-gray-400">Last seen: {new Date(onu.last_seen).toLocaleString()}</p>
        <div className="flex gap-2">
          {onu.latitude && onu.longitude && (
            <button
              onClick={() => window.open(`https://www.google.com/maps?q=${onu.latitude},${onu.longitude}`, '_blank')}
              className="px-3 py-1.5 text-sm bg-emerald-500 text-white rounded-lg font-medium shadow-sm hover:bg-emerald-600 transition-colors"
            >
              Map
            </button>
          )}
          <button
            onClick={() => onEdit(onu)}
            className="px-3 py-1.5 text-sm bg-primary-500 text-white rounded-lg font-medium shadow-sm hover:bg-primary-600 transition-colors"
          >
            Edit
          </button>
          {isAdmin && (
            <button
              onClick={() => {
                if (window.confirm('Delete this ONU?')) onDelete(onu.id);
              }}
              className="px-3 py-1.5 text-sm bg-red-500 text-white rounded-lg font-medium shadow-sm hover:bg-red-600 transition-colors"
            >
              Delete
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// Splitter Simulator Component - Interactive Visual Diagram
function SplitterSimulator({ olts = [], onus = [] }) {
  // Splitter types with loss values
  const splitterTypes = {
    '1:2': { ports: 2, loss: 3.8, category: 'PLC' },
    '1:4': { ports: 4, loss: 7.2, category: 'PLC' },
    '1:8': { ports: 8, loss: 10.5, category: 'PLC' },
    '1:16': { ports: 16, loss: 14.0, category: 'PLC' },
    '1:32': { ports: 32, loss: 17.5, category: 'PLC' },
    '50/50': { ports: 2, loss: 3.5, category: 'FBT', portLosses: [3.5, 3.5] },
    '30/70': { ports: 2, loss: null, category: 'FBT', portLosses: [5.2, 1.5] },
    '20/80': { ports: 2, loss: null, category: 'FBT', portLosses: [7.0, 1.0] },
    '10/90': { ports: 2, loss: null, category: 'FBT', portLosses: [10.0, 0.5] },
  };

  // Canvas state
  const canvasRef = useRef(null);
  const [canvasSize, setCanvasSize] = useState({ width: 1200, height: 700 });

  // Multiple diagrams support
  const [diagrams, setDiagrams] = useState(() => {
    try {
      const saved = localStorage.getItem('splitterDiagrams');
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {}
    return [{ id: 'default', name: 'Diagram 1', nodes: [], connections: [], settings: { oltPower: 5, onuSensitivity: -28 } }];
  });

  const [currentDiagramId, setCurrentDiagramId] = useState(() => {
    try {
      const saved = localStorage.getItem('currentDiagramId');
      return saved || 'default';
    } catch (e) {}
    return 'default';
  });

  const [showDiagramMenu, setShowDiagramMenu] = useState(false);
  const [editingDiagramName, setEditingDiagramName] = useState(null);
  const [newDiagramName, setNewDiagramName] = useState('');

  // Get current diagram
  const currentDiagram = diagrams.find(d => d.id === currentDiagramId) || diagrams[0];

  // Nodes and connections from current diagram
  const [nodes, setNodes] = useState(currentDiagram?.nodes || []);
  const [connections, setConnections] = useState(currentDiagram?.connections || []);

  // Update nodes/connections when switching diagrams
  useEffect(() => {
    const diagram = diagrams.find(d => d.id === currentDiagramId);
    if (diagram) {
      setNodes(diagram.nodes || []);
      setConnections(diagram.connections || []);
      setOltPower(diagram.settings?.oltPower || 5);
      setOnuSensitivity(diagram.settings?.onuSensitivity || -28);
    }
    localStorage.setItem('currentDiagramId', currentDiagramId);
  }, [currentDiagramId]);

  const [selectedNode, setSelectedNode] = useState(null);
  const [draggingNode, setDraggingNode] = useState(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  // Connection drawing state
  const [connecting, setConnecting] = useState(null); // { nodeId, portType, portIndex }
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // Settings
  const [oltPower, setOltPower] = useState(currentDiagram?.settings?.oltPower || 5);
  const [fiberLossPerKm, setFiberLossPerKm] = useState(0.35);
  const [connectorLoss, setConnectorLoss] = useState(0.5);
  const [onuSensitivity, setOnuSensitivity] = useState(currentDiagram?.settings?.onuSensitivity || -28);

  // Auto-save to localStorage whenever nodes, connections, or settings change
  const [lastSaved, setLastSaved] = useState(null);
  const [saveStatus, setSaveStatus] = useState('idle'); // 'idle', 'saving', 'saved'

  // Create new diagram
  const createNewDiagram = () => {
    const newId = `diagram-${Date.now()}`;
    const newDiagram = {
      id: newId,
      name: `Diagram ${diagrams.length + 1}`,
      nodes: [],
      connections: [],
      settings: { oltPower: 5, onuSensitivity: -28 }
    };
    setDiagrams([...diagrams, newDiagram]);
    setCurrentDiagramId(newId);
    setNodes([]);
    setConnections([]);
    setShowDiagramMenu(false);
  };

  // Rename diagram
  const renameDiagram = (id, newName) => {
    setDiagrams(diagrams.map(d => d.id === id ? { ...d, name: newName } : d));
    setEditingDiagramName(null);
  };

  // Delete diagram
  const deleteDiagram = (id) => {
    if (diagrams.length <= 1) {
      alert('Cannot delete the last diagram');
      return;
    }
    if (window.confirm('Delete this diagram?')) {
      const newDiagrams = diagrams.filter(d => d.id !== id);
      setDiagrams(newDiagrams);
      if (currentDiagramId === id) {
        setCurrentDiagramId(newDiagrams[0].id);
      }
    }
  };

  // Switch diagram
  const switchDiagram = (id) => {
    // Save current diagram first
    const updatedDiagrams = diagrams.map(d =>
      d.id === currentDiagramId
        ? { ...d, nodes, connections, settings: { oltPower, onuSensitivity } }
        : d
    );
    setDiagrams(updatedDiagrams);
    setCurrentDiagramId(id);
    setShowDiagramMenu(false);
  };

  useEffect(() => {
    // Save current diagram to diagrams array
    if (nodes.length > 0 || connections.length > 0) {
      setSaveStatus('saving');
      const updatedDiagrams = diagrams.map(d =>
        d.id === currentDiagramId
          ? { ...d, nodes, connections, settings: { oltPower, onuSensitivity }, savedAt: new Date().toISOString() }
          : d
      );
      setDiagrams(updatedDiagrams);
      localStorage.setItem('splitterDiagrams', JSON.stringify(updatedDiagrams));
      setLastSaved(new Date());
      setSaveStatus('saved');
      const timer = setTimeout(() => setSaveStatus('idle'), 2000);
      return () => clearTimeout(timer);
    }
  }, [nodes, connections, oltPower, onuSensitivity]);

  // Also save diagrams when they change
  useEffect(() => {
    localStorage.setItem('splitterDiagrams', JSON.stringify(diagrams));
  }, [diagrams]);

  // Legacy: migrate old single diagram to new format
  useEffect(() => {
    try {
      const oldSaved = localStorage.getItem('splitterDiagram');
      if (oldSaved && !localStorage.getItem('splitterDiagrams')) {
        const oldData = JSON.parse(oldSaved);
        if (oldData.nodes?.length > 0) {
          const migratedDiagram = {
            id: 'migrated',
            name: 'Migrated Diagram',
            nodes: oldData.nodes,
            connections: oldData.connections,
            settings: oldData.settings || { oltPower: 5, onuSensitivity: -28 }
          };
          setDiagrams([migratedDiagram]);
          setCurrentDiagramId('migrated');
          setNodes(oldData.nodes);
          setConnections(oldData.connections);
          localStorage.removeItem('splitterDiagram');
        }
      }
    } catch (e) {}
  }, []);

  // Clear diagram function
  const clearDiagram = () => {
    if (window.confirm('Clear the current diagram? This cannot be undone.')) {
      setNodes([]);
      setConnections([]);
      setSelectedNode(null);
    }
  };

  // OLT and PON selection
  const [selectedOltId, setSelectedOltId] = useState(olts[0]?.id || null);
  const [selectedPonPort, setSelectedPonPort] = useState(1);
  const [showOnuPicker, setShowOnuPicker] = useState(false);

  // Get selected OLT
  const selectedOlt = olts.find(o => o.id === selectedOltId);

  // Get ONUs for selected OLT and PON
  const filteredOnus = onus.filter(o =>
    o.olt_id === selectedOltId && o.pon_port === selectedPonPort
  );

  // Add OLT node
  const addOLT = () => {
    if (!selectedOlt) return;
    
    const newNode = {
      id: `olt-${Date.now()}`,
      type: 'olt',
      name: selectedOlt.name,
      x: 50,
      y: 200,
      width: 130,
      height: 50 + selectedOlt.pon_ports * 12,
      ponPorts: selectedOlt.pon_ports || 8,
      power: oltPower,
      oltId: selectedOlt.id,
      ipAddress: selectedOlt.ip_address,
    };
    setNodes([...nodes, newNode]);
  };

  // Add Splitter node
  const addSplitter = (type = '1:8') => {
    
    const splitterDef = splitterTypes[type];
    const newNode = {
      id: `splitter-${Date.now()}`,
      type: 'splitter',
      name: type,
      splitterType: type,
      x: 220 + nodes.filter(n => n.type === 'splitter').length * 100,
      y: 200,
      width: 65,
      height: 35 + splitterDef.ports * 10,
      inputPorts: 1,
      outputPorts: splitterDef.ports,
      category: splitterDef.category,
      loss: splitterDef.loss,
      portLosses: splitterDef.portLosses,
      brand: 'Generic',
      fiberLength: 0.5, // km from input
    };
    setNodes([...nodes, newNode]);
  };

  // Add ONU node from selected ONU
  const addONU = (onu) => {
    if (!onu) return;
    // Check if this ONU is already added
    if (nodes.some(n => n.onuId === onu.id)) {
      alert('This ONU is already on the diagram');
      return;
    }
    
    const onuCount = nodes.filter(n => n.type === 'onu').length;
    const newNode = {
      id: `onu-${Date.now()}`,
      type: 'onu',
      name: onu.description || onu.mac_address,
      x: 450 + (onuCount % 4) * 100,
      y: 80 + Math.floor(onuCount / 4) * 70,
      width: 85,
      height: 55,
      onuId: onu.id,
      mac: onu.mac_address,
      distance: onu.distance || 0,
      rxPower: onu.rx_power,
      sensitivity: onuSensitivity,
      ponPort: onu.pon_port,
      onuNumber: onu.onu_id,
    };
    setNodes([...nodes, newNode]);
    setShowOnuPicker(false);
  };

  // Add generic ONU (not from list)
  const addGenericONU = () => {

    const onuCount = nodes.filter(n => n.type === 'onu').length;
    const newNode = {
      id: `onu-${Date.now()}`,
      type: 'onu',
      name: `ONU ${onuCount + 1}`,
      x: 450 + (onuCount % 4) * 100,
      y: 80 + Math.floor(onuCount / 4) * 70,
      width: 85,
      height: 55,
      onuId: null,
      mac: '',
      distance: 500,
      rxPower: null,
      sensitivity: onuSensitivity,
    };
    setNodes([...nodes, newNode]);
    setShowOnuPicker(false);
  };

  // Add Layer 2 Switch with multiple output ports
  const addSwitch = (ports) => {
    const switchCount = nodes.filter(n => n.type === 'switch').length;
    const newNode = {
      id: `switch-${Date.now()}`,
      type: 'switch',
      name: `Switch ${switchCount + 1}`,
      x: 600 + (switchCount % 3) * 150,
      y: 100 + Math.floor(switchCount / 3) * 250,
      width: 120,
      height: 30 + ports * 22, // Height based on number of ports
      ports: ports,
      uplinkPort: 1,
    };
    setNodes([...nodes, newNode]);
  };

  // Add Building with 12 floors and 2 homes per floor
  const addBuilding = () => {
    const buildingCount = nodes.filter(n => n.type === 'building').length;
    // Create 12 floors with 2 homes each (24 units total)
    const floors = {};
    for (let f = 1; f <= 12; f++) {
      floors[f] = {
        home1: { customer: '', unit: `${f}A` },
        home2: { customer: '', unit: `${f}B` },
      };
    }
    const newNode = {
      id: `building-${Date.now()}`,
      type: 'building',
      name: `Building ${buildingCount + 1}`,
      floors: floors,
      totalFloors: 12,
      x: 800 + (buildingCount % 3) * 180,
      y: 100 + Math.floor(buildingCount / 3) * 350,
      width: 160,
      height: 320,
    };
    setNodes([...nodes, newNode]);
  };

  // Delete node
  const deleteNode = (nodeId) => {
    setNodes(nodes.filter(n => n.id !== nodeId));
    setConnections(connections.filter(c => c.from.nodeId !== nodeId && c.to.nodeId !== nodeId));
    setSelectedNode(null);
  };

  // Get port position
  const getPortPosition = (node, portType, portIndex) => {
    if (node.type === 'olt') {
      // PON ports on right side
      const portSpacing = (node.height - 40) / node.ponPorts;
      return {
        x: node.x + node.width,
        y: node.y + 30 + portIndex * portSpacing + portSpacing / 2,
      };
    } else if (node.type === 'splitter') {
      if (portType === 'input') {
        return { x: node.x, y: node.y + node.height / 2 };
      } else {
        const portSpacing = (node.height - 20) / node.outputPorts;
        return {
          x: node.x + node.width,
          y: node.y + 15 + portIndex * portSpacing + portSpacing / 2,
        };
      }
    } else if (node.type === 'onu') {
      if (portType === 'input') {
        return { x: node.x, y: node.y + node.height / 2 };
      } else {
        // Output port on right side for connecting to switch
        return { x: node.x + node.width, y: node.y + node.height / 2 };
      }
    } else if (node.type === 'switch') {
      if (portType === 'input') {
        // Uplink port on left side at top
        return { x: node.x, y: node.y + 20 };
      } else {
        // Output ports on right side - one for each port
        const portSpacing = 22;
        return {
          x: node.x + node.width,
          y: node.y + 30 + portIndex * portSpacing + portSpacing / 2,
        };
      }
    } else if (node.type === 'building') {
      // Input ports on left side for each floor
      const totalFloors = node.totalFloors || 12;
      const floorHeight = (node.height - 50) / totalFloors;
      // portIndex is the floor number (1-based), convert to position from top
      const floorFromTop = totalFloors - portIndex;
      return {
        x: node.x,
        y: node.y + 30 + floorFromTop * floorHeight + floorHeight / 2,
      };
    }
    return { x: node.x, y: node.y };
  };

  // Handle mouse down on port
  const handlePortMouseDown = (e, node, portType, portIndex) => {
    e.stopPropagation();
    setConnecting({ nodeId: node.id, portType, portIndex });
  };

  // Handle mouse up - complete connection
  const handlePortMouseUp = (e, node, portType, portIndex) => {
    e.stopPropagation();
    if (connecting && connecting.nodeId !== node.id) {
      // Check valid connection
      const fromNode = nodes.find(n => n.id === connecting.nodeId);
      const toNode = node;

      // Valid connections:
      // OLT output -> Splitter input
      // Splitter output -> Splitter input, ONU input
      // ONU output -> Switch input
      // Switch output -> Building input
      let isValid = false;
      if (fromNode.type === 'olt' && toNode.type === 'splitter' && portType === 'input') {
        isValid = true;
      } else if (fromNode.type === 'splitter' && connecting.portType === 'output') {
        if (toNode.type === 'splitter' && portType === 'input') isValid = true;
        if (toNode.type === 'onu' && portType === 'input') isValid = true;
      } else if (fromNode.type === 'onu' && connecting.portType === 'output') {
        if (toNode.type === 'switch' && portType === 'input') isValid = true;
      } else if (fromNode.type === 'switch' && connecting.portType === 'output') {
        if (toNode.type === 'building' && portType === 'input') isValid = true;
      }

      if (isValid) {
        // Check if this exact connection already exists (same from AND same to)
        const duplicateConn = connections.find(c =>
          c.from.nodeId === connecting.nodeId &&
          c.from.portIndex === connecting.portIndex &&
          c.from.portType === connecting.portType &&
          c.to.nodeId === node.id &&
          c.to.portIndex === portIndex &&
          c.to.portType === portType
        );

        // Check if destination input port already has a connection (only one cable per input)
        const destHasConnection = connections.find(c =>
          c.to.nodeId === node.id && c.to.portIndex === portIndex && c.to.portType === portType
        );

        // Allow connection if: not duplicate AND destination input is free
        // OLT/Splitter output ports can have multiple cables (to different destinations)
        if (!duplicateConn && !destHasConnection) {
          setConnections([...connections, {
            id: `conn-${Date.now()}`,
            from: { nodeId: connecting.nodeId, portType: connecting.portType, portIndex: connecting.portIndex },
            to: { nodeId: node.id, portType: portType, portIndex: portIndex },
            cableLength: 500,
            connectors: 2,
          }]);
        }
      }
    }
    setConnecting(null);
  };

  // Handle canvas mouse move
  const handleCanvasMouseMove = (e) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (rect) {
      setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    }

    if (draggingNode) {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (rect) {
        const x = e.clientX - rect.left - dragOffset.x;
        const y = e.clientY - rect.top - dragOffset.y;
        setNodes(nodes.map(n => n.id === draggingNode.id ? { ...n, x: Math.max(0, x), y: Math.max(0, y) } : n));
      }
    }
  };

  // Handle node mouse down (for dragging)
  const handleNodeMouseDown = (e, node) => {
    if (e.target.classList.contains('port')) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (rect) {
      setDraggingNode(node);
      setDragOffset({ x: e.clientX - rect.left - node.x, y: e.clientY - rect.top - node.y });
    }
    setSelectedNode(node);
  };

  // Handle mouse up
  const handleCanvasMouseUp = () => {
    setDraggingNode(null);
    setConnecting(null);
  };

  // Delete connection
  const deleteConnection = (connId) => {
    setConnections(connections.filter(c => c.id !== connId));
  };

  // Calculate power at each node
  const calculatePower = () => {
    const powerMap = {};

    // Find OLT
    const oltNode = nodes.find(n => n.type === 'olt');
    if (!oltNode) return powerMap;

    // BFS from OLT
    const queue = [];

    // Initialize OLT ports
    for (let i = 0; i < oltNode.ponPorts; i++) {
      powerMap[`${oltNode.id}-output-${i}`] = oltPower;

      // Find connections from this port
      const conns = connections.filter(c => c.from.nodeId === oltNode.id && c.from.portIndex === i);
      conns.forEach(conn => {
        queue.push({ conn, power: oltPower });
      });
    }

    while (queue.length > 0) {
      const { conn, power } = queue.shift();

      // Calculate loss through connection (cableLength is in meters)
      const cableLengthKm = (conn.cableLength || 500) / 1000;
      const fiberLoss = cableLengthKm * fiberLossPerKm;
      const connLoss = (conn.connectors || 2) * connectorLoss;
      let currentPower = power - fiberLoss - connLoss;

      const toNode = nodes.find(n => n.id === conn.to.nodeId);
      if (!toNode) continue;

      // Store power at input
      powerMap[`${toNode.id}-input`] = currentPower;

      if (toNode.type === 'splitter') {
        // Calculate splitter loss and output power
        const splitterDef = splitterTypes[toNode.splitterType];

        for (let i = 0; i < toNode.outputPorts; i++) {
          let portLoss = splitterDef.loss;
          if (splitterDef.portLosses) {
            portLoss = splitterDef.portLosses[i] || splitterDef.portLosses[0];
          }
          const outputPower = currentPower - portLoss;
          powerMap[`${toNode.id}-output-${i}`] = outputPower;

          // Find connections from this output
          const outConns = connections.filter(c => c.from.nodeId === toNode.id && c.from.portIndex === i);
          outConns.forEach(outConn => {
            queue.push({ conn: outConn, power: outputPower });
          });
        }
      } else if (toNode.type === 'onu') {
        powerMap[`${toNode.id}-rx`] = currentPower;
      }
    }

    return powerMap;
  };

  const powerMap = calculatePower();

  // Get status color based on power
  const getPowerStatus = (power) => {
    if (power === undefined) return { color: '#9CA3AF', status: 'N/A' };
    const margin = power - onuSensitivity;
    if (margin >= 3) return { color: '#10B981', status: 'GOOD' };
    if (margin >= 0) return { color: '#F59E0B', status: 'MARGINAL' };
    return { color: '#EF4444', status: 'FAIL' };
  };

  // Update connection fiber length
  const updateConnection = (connId, field, value) => {
    setConnections(connections.map(c => c.id === connId ? { ...c, [field]: value } : c));
  };

  // Update node
  const updateNode = (nodeId, field, value) => {
    setNodes(nodes.map(n => n.id === nodeId ? { ...n, [field]: value } : n));
  };

  return (
    <div className="space-y-2">
      {/* Click outside to close menu */}
      {showDiagramMenu && (
        <div className="fixed inset-0 z-[99]" onClick={() => setShowDiagramMenu(false)} />
      )}

      {/* OLT/PON Selection Bar with Diagram Selector */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg shadow-md px-3 py-2">
        <div className="flex flex-wrap gap-3 items-center">
          {/* Diagram Selector */}
          <div className="relative">
            <button
              onClick={() => setShowDiagramMenu(!showDiagramMenu)}
              className="flex items-center gap-2 px-3 py-1.5 bg-white/20 text-white border border-white/30 rounded-lg text-sm font-medium backdrop-blur hover:bg-white/30"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
              {currentDiagram?.name || 'Diagram'}
              <svg className={`w-3 h-3 transition-transform ${showDiagramMenu ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Dropdown Menu */}
            {showDiagramMenu && (
              <div className="absolute left-0 mt-2 w-72 bg-white rounded-xl shadow-xl border border-gray-200 z-[100] overflow-hidden">
                <div className="p-3 bg-gray-50 border-b border-gray-200">
                  <h4 className="font-semibold text-gray-700 text-sm">Your Diagrams</h4>
                </div>
                <div className="max-h-64 overflow-y-auto">
                  {diagrams.map(diagram => (
                    <div
                      key={diagram.id}
                      className={`flex items-center gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer border-b border-gray-100 ${diagram.id === currentDiagramId ? 'bg-purple-50' : ''}`}
                    >
                      {editingDiagramName === diagram.id ? (
                        <input
                          type="text"
                          defaultValue={diagram.name}
                          autoFocus
                          className="flex-1 px-2 py-1 border border-purple-300 rounded text-sm"
                          onBlur={(e) => renameDiagram(diagram.id, e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') renameDiagram(diagram.id, e.target.value);
                            if (e.key === 'Escape') setEditingDiagramName(null);
                          }}
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <>
                          <div className="flex-1" onClick={() => switchDiagram(diagram.id)}>
                            <p className={`font-medium ${diagram.id === currentDiagramId ? 'text-purple-700' : 'text-gray-700'}`}>
                              {diagram.name}
                            </p>
                            <p className="text-xs text-gray-400">
                              {diagram.nodes?.length || 0} items, {diagram.connections?.length || 0} cables
                            </p>
                          </div>
                          <button
                            onClick={(e) => { e.stopPropagation(); setEditingDiagramName(diagram.id); }}
                            className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                            title="Rename"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                            </svg>
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); deleteDiagram(diagram.id); }}
                            className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                            title="Delete"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </>
                      )}
                    </div>
                  ))}
                </div>
                <div className="p-3 border-t border-gray-200">
                  <button
                    onClick={createNewDiagram}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    New Diagram
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="border-l border-white/30 h-6"></div>

          <select
            value={selectedOltId || ''}
            onChange={(e) => { setSelectedOltId(parseInt(e.target.value) || null); setSelectedPonPort(1); }}
            className="px-3 py-1.5 bg-white/20 text-white border border-white/30 rounded-lg text-sm font-medium backdrop-blur focus:outline-none"
          >
            <option value="" className="text-gray-800">Select OLT</option>
            {olts.map(olt => (
              <option key={olt.id} value={olt.id} className="text-gray-800">
                {olt.name} ({olt.ip_address})
              </option>
            ))}
          </select>

          {selectedOlt && (
            <select
              value={selectedPonPort}
              onChange={(e) => setSelectedPonPort(parseInt(e.target.value))}
              className="px-3 py-1.5 bg-white/20 text-white border border-white/30 rounded-lg text-sm font-medium backdrop-blur focus:outline-none"
            >
              {Array.from({ length: selectedOlt.pon_ports || 8 }, (_, i) => i + 1).map(p => {
                const onuCount = onus.filter(o => o.olt_id === selectedOltId && o.pon_port === p).length;
                return (
                  <option key={p} value={p} className="text-gray-800">
                    PON {p} ({onuCount})
                  </option>
                );
              })}
            </select>
          )}

          {selectedOlt && (
            <span className="px-2 py-1 bg-white/20 rounded text-white text-xs ml-auto">
              {filteredOnus.length} ONUs
            </span>
          )}
        </div>
      </div>

      {/* Toolbar - Compact */}
      <div className="bg-white rounded-lg shadow-md p-2 space-y-2">
        {/* Row 1: Add components */}
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm font-medium text-gray-600">Add:</span>

          <button
            onClick={addOLT}
            disabled={!selectedOlt}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
            </svg>
            {selectedOlt?.name || 'OLT'}
          </button>

          <div className="flex items-center gap-2">
            <select
              id="splitterType"
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              defaultValue="1:8"
            >
              <optgroup label="PLC Splitters">
                <option value="1:2">1:2 (3.8 dB)</option>
                <option value="1:4">1:4 (7.2 dB)</option>
                <option value="1:8">1:8 (10.5 dB)</option>
                <option value="1:16">1:16 (14.0 dB)</option>
                <option value="1:32">1:32 (17.5 dB)</option>
              </optgroup>
              <optgroup label="FBT Splitters">
                <option value="50/50">50/50 (3.5 dB)</option>
                <option value="30/70">30/70 (5.2/1.5 dB)</option>
                <option value="20/80">20/80 (7.0/1.0 dB)</option>
                <option value="10/90">10/90 (10.0/0.5 dB)</option>
              </optgroup>
            </select>
            <button
              onClick={() => addSplitter(document.getElementById('splitterType').value)}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center gap-2 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Splitter
            </button>
          </div>

          <button
            onClick={() => setShowOnuPicker(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
            </svg>
            ONU
          </button>

          <div className="border-l border-gray-300 h-8 mx-2"></div>

          {/* Switch buttons */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => addSwitch(8)}
              className="px-3 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 flex items-center gap-1 transition-colors text-sm"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              SW-8
            </button>
            <button
              onClick={() => addSwitch(16)}
              className="px-3 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 flex items-center gap-1 transition-colors text-sm"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              SW-16
            </button>
          </div>

          {/* Building button */}
          <button
            onClick={addBuilding}
            className="px-3 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center gap-1 transition-colors text-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            Building
          </button>

          <div className="border-l border-gray-300 h-8 mx-2"></div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">OLT Power:</label>
            <input
              type="number"
              value={oltPower}
              onChange={(e) => setOltPower(parseFloat(e.target.value) || 5)}
              className="w-16 px-2 py-1 border border-gray-300 rounded text-sm"
              step="0.5"
            />
            <span className="text-sm text-gray-500">dBm</span>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">ONU Sens:</label>
            <input
              type="number"
              value={onuSensitivity}
              onChange={(e) => setOnuSensitivity(parseFloat(e.target.value) || -28)}
              className="w-16 px-2 py-1 border border-gray-300 rounded text-sm"
              step="0.5"
            />
            <span className="text-sm text-gray-500">dBm</span>
          </div>

          {selectedNode && selectedNode.type !== 'connection' && (
            <button
              onClick={() => deleteNode(selectedNode.id)}
              className="px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2 transition-colors text-sm"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete
            </button>
          )}
        </div>

        {/* Row 2: Auto-save status and Clear */}
        <div className="flex flex-wrap gap-3 items-center pt-2 border-t border-gray-200">
          {/* Auto-save status indicator */}
          <div className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-300 ${
            saveStatus === 'saving' ? 'bg-yellow-100 border border-yellow-300' :
            saveStatus === 'saved' ? 'bg-green-100 border border-green-300' :
            'bg-gray-100 border border-gray-200'
          }`}>
            {saveStatus === 'saving' ? (
              <>
                <svg className="w-5 h-5 text-yellow-600 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span className="text-sm font-medium text-yellow-700">Saving...</span>
              </>
            ) : saveStatus === 'saved' ? (
              <>
                <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span className="text-sm font-medium text-green-700">Auto-saved!</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                </svg>
                <span className="text-sm font-medium text-gray-600">Auto-save enabled</span>
              </>
            )}
          </div>

          {/* Item count */}
          <div className="bg-blue-50 border border-blue-200 px-3 py-2 rounded-lg">
            <span className="text-sm font-medium text-blue-700">
              📊 {nodes.length} items, {connections.length} cables
            </span>
          </div>

          {/* Clear button */}
          <button
            onClick={clearDiagram}
            className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 text-sm font-medium flex items-center gap-2 transition-colors ml-auto"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Clear All
          </button>
        </div>
      </div>

      {/* ONU Picker Modal */}
      {showOnuPicker && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowOnuPicker(false)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="bg-gradient-to-r from-green-600 to-emerald-600 p-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                  </svg>
                  Select ONU
                </h3>
                <button onClick={() => setShowOnuPicker(false)} className="text-white/80 hover:text-white">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <p className="text-green-100 text-sm mt-1">
                {selectedOlt?.name} → PON {selectedPonPort} ({filteredOnus.length} ONUs)
              </p>
            </div>

            <div className="p-4 max-h-[60vh] overflow-y-auto">
              {/* Add Generic ONU option with distance input */}
              <div className="mb-4 p-4 border-2 border-dashed border-gray-300 rounded-xl bg-gray-50">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 bg-green-500 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  </div>
                  <div className="text-left flex-1">
                    <p className="font-bold text-gray-800">Add Generic ONU</p>
                    <p className="text-sm text-gray-500">Set distance to calculate expected power</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <label className="block text-xs text-gray-500 mb-1">Distance (meters)</label>
                    <input
                      type="number"
                      id="genericOnuDistance"
                      defaultValue={500}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-bold"
                      placeholder="e.g. 500"
                      step="50"
                      min="0"
                    />
                  </div>
                  <div className="flex-1">
                    <label className="block text-xs text-gray-500 mb-1">Expected Loss</label>
                    <p className="px-3 py-2 bg-orange-100 rounded-lg text-sm font-bold text-orange-700">
                      ~{((parseInt(document.getElementById('genericOnuDistance')?.value || 500) / 1000) * 0.35).toFixed(2)} dB
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      const distanceInput = document.getElementById('genericOnuDistance');
                      const distance = distanceInput ? parseInt(distanceInput.value) || 500 : 500;
                      const onuCount = nodes.filter(n => n.type === 'onu').length;
                      const newNode = {
                        id: `onu-${Date.now()}`,
                        type: 'onu',
                        name: `ONU ${onuCount + 1}`,
                        x: 450 + (onuCount % 4) * 100,
                        y: 80 + Math.floor(onuCount / 4) * 70,
                        width: 85,
                        height: 55,
                        onuId: null,
                        mac: '',
                        distance: distance,
                        rxPower: null,
                        sensitivity: onuSensitivity,
                      };
                      setNodes([...nodes, newNode]);
                      setShowOnuPicker(false);
                    }}
                    className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium flex items-center gap-2"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Add
                  </button>
                </div>
              </div>

              {filteredOnus.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 12h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p>No ONUs found on this PON port</p>
                  <p className="text-sm mt-1">Select a different PON port or add a generic ONU</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredOnus.map(onu => {
                    const isAdded = nodes.some(n => n.onuId === onu.id);
                    return (
                      <button
                        key={onu.id}
                        onClick={() => addONU(onu)}
                        disabled={isAdded}
                        className={`w-full p-3 rounded-xl border-2 transition-all flex items-center gap-3 ${
                          isAdded
                            ? 'border-gray-200 bg-gray-50 cursor-not-allowed opacity-60'
                            : 'border-gray-200 hover:border-green-500 hover:bg-green-50'
                        }`}
                      >
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                          onu.is_online ? 'bg-green-500' : 'bg-red-500'
                        }`}>
                          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                          </svg>
                        </div>
                        <div className="flex-1 text-left">
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-gray-800">{onu.description || 'No Name'}</p>
                            {isAdded && (
                              <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">Added</span>
                            )}
                          </div>
                          <p className="text-sm text-gray-500 font-mono">{onu.mac_address}</p>
                        </div>
                        <div className="text-right text-sm">
                          {onu.distance && (
                            <p className="text-gray-600">{onu.distance}m</p>
                          )}
                          {onu.rx_power && (
                            <p className={`font-medium ${onu.rx_power > -25 ? 'text-green-600' : onu.rx_power > -28 ? 'text-yellow-600' : 'text-red-600'}`}>
                              {onu.rx_power} dBm
                            </p>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Canvas - Full height */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div
          ref={canvasRef}
          className="relative bg-gray-50 overflow-auto"
          style={{ height: 'calc(100vh - 280px)', minHeight: '500px', cursor: connecting ? 'crosshair' : 'default' }}
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
          onMouseLeave={handleCanvasMouseUp}
        >
          {/* Grid background */}
          <svg className="absolute inset-0 w-full h-full" style={{ minWidth: canvasSize.width, minHeight: canvasSize.height }}>
            <defs>
              <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#E5E7EB" strokeWidth="0.5"/>
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" style={{ pointerEvents: 'none' }} />

            {/* Draw connections */}
            {connections.map(conn => {
              const fromNode = nodes.find(n => n.id === conn.from.nodeId);
              const toNode = nodes.find(n => n.id === conn.to.nodeId);
              if (!fromNode || !toNode) return null;

              const fromPos = getPortPosition(fromNode, conn.from.portType, conn.from.portIndex);
              const toPos = getPortPosition(toNode, conn.to.portType, conn.to.portIndex);

              // Check if this is an ethernet cable (ONU->Switch or Switch->Building)
              const isEthernetCable = (fromNode.type === 'onu' && toNode.type === 'switch') ||
                                      (fromNode.type === 'switch' && toNode.type === 'building');

              // Calculate power at destination (only for fiber cables)
              const destPower = !isEthernetCable ? powerMap[`${toNode.id}-${toNode.type === 'onu' ? 'rx' : 'input'}`] : undefined;
              const status = isEthernetCable ? { color: '#F59E0B' } : getPowerStatus(destPower); // Yellow for ethernet

              // Label position with offset - the control point for the curve
              const defaultMidX = (fromPos.x + toPos.x) / 2;
              const defaultMidY = (fromPos.y + toPos.y) / 2;
              const labelOffsetX = conn.labelOffsetX || 0;
              const labelOffsetY = conn.labelOffsetY || 0;

              // Control point (where user drags to)
              const controlX = defaultMidX + labelOffsetX * 2; // Double the offset for control point
              const controlY = defaultMidY + labelOffsetY * 2;

              // The actual point on quadratic bezier at t=0.5 (middle of curve)
              // B(0.5) = 0.25*P0 + 0.5*P1 + 0.25*P2
              const labelX = 0.25 * fromPos.x + 0.5 * controlX + 0.25 * toPos.x;
              const labelY = 0.25 * fromPos.y + 0.5 * controlY + 0.25 * toPos.y;

              // Cable path with control point
              const path = `M ${fromPos.x} ${fromPos.y} Q ${controlX} ${controlY}, ${toPos.x} ${toPos.y}`;

              const isSelected = selectedNode?.type === 'connection' && selectedNode?.id === conn.id;
              const cableLengthMeters = (conn.cableLength || (isEthernetCable ? 50 : 500)); // Default 50m for ethernet, 500m for fiber
              const cableLoss = (cableLengthMeters / 1000) * fiberLossPerKm;

              return (
                <g key={conn.id}>
                  {/* Cable path - wider hit area */}
                  <path
                    d={path}
                    fill="none"
                    stroke="transparent"
                    strokeWidth="15"
                    className="cursor-pointer"
                    onClick={() => setSelectedNode({ type: 'connection', ...conn })}
                  />
                  {/* Visible cable */}
                  <path
                    d={path}
                    fill="none"
                    stroke={isSelected ? '#3B82F6' : status.color}
                    strokeWidth={isSelected ? 4 : 3}
                    strokeDasharray={isEthernetCable ? '8,4' : 'none'}
                    className="pointer-events-none"
                  />
                  {/* Cable info box with editable distance - DRAGGABLE */}
                  <foreignObject
                    x={labelX - 45}
                    y={labelY - (isEthernetCable ? 18 : 28)}
                    width="90"
                    height={isEthernetCable ? 36 : 56}
                    style={{ overflow: 'visible' }}
                  >
                    <div
                      className={`flex flex-col items-center justify-center p-1 rounded-lg border-2 shadow-md ${
                        isSelected ? 'bg-blue-500 border-blue-600' : isEthernetCable ? 'bg-yellow-50 border-yellow-400' : 'bg-white border-gray-300'
                      }`}
                      style={{ height: isEthernetCable ? '32px' : '52px', cursor: 'grab' }}
                      draggable={false}
                      onMouseDown={(e) => {
                        if (e.target.tagName === 'INPUT') return;
                        e.preventDefault();
                        e.stopPropagation();

                        const startX = e.clientX;
                        const startY = e.clientY;
                        const startOffsetX = conn.labelOffsetX || 0;
                        const startOffsetY = conn.labelOffsetY || 0;

                        e.target.style.cursor = 'grabbing';

                        const handleMouseMove = (moveE) => {
                          moveE.preventDefault();
                          const dx = moveE.clientX - startX;
                          const dy = moveE.clientY - startY;
                          updateConnection(conn.id, 'labelOffsetX', startOffsetX + dx);
                          updateConnection(conn.id, 'labelOffsetY', startOffsetY + dy);
                        };

                        const handleMouseUp = (upE) => {
                          upE.target.style.cursor = 'grab';
                          document.removeEventListener('mousemove', handleMouseMove);
                          document.removeEventListener('mouseup', handleMouseUp);
                        };

                        document.addEventListener('mousemove', handleMouseMove);
                        document.addEventListener('mouseup', handleMouseUp);
                      }}
                      title="Drag to move"
                    >
                      <div className="flex items-center gap-0.5">
                        <input
                          type="number"
                          value={cableLengthMeters}
                          onChange={(e) => {
                            e.stopPropagation();
                            updateConnection(conn.id, 'cableLength', parseInt(e.target.value) || 0);
                          }}
                          onClick={(e) => e.stopPropagation()}
                          onMouseDown={(e) => e.stopPropagation()}
                          className={`w-14 px-1 py-0.5 text-center text-xs font-bold rounded border ${
                            isSelected
                              ? 'bg-blue-400 border-blue-300 text-white placeholder-blue-200'
                              : 'bg-gray-50 border-gray-300 text-gray-800'
                          }`}
                          style={{ fontSize: '11px' }}
                          step={isEthernetCable ? 10 : 50}
                          min="0"
                        />
                        <span className={`text-xs font-medium ${isSelected ? 'text-white' : 'text-gray-600'}`}>m</span>
                      </div>
                      {!isEthernetCable && (
                        <div className={`text-xs mt-0.5 font-medium ${isSelected ? 'text-blue-100' : 'text-orange-600'}`}>
                          -{cableLoss.toFixed(2)} dB
                        </div>
                      )}
                    </div>
                  </foreignObject>
                  {/* Delete button - using foreignObject for HTML button */}
                  <foreignObject
                    x={labelX + 40}
                    y={labelY - 15}
                    width="28"
                    height="28"
                  >
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        e.preventDefault();
                        deleteConnection(conn.id);
                        setSelectedNode(null);
                      }}
                      className="w-6 h-6 bg-red-500 hover:bg-red-600 text-white rounded-full flex items-center justify-center text-sm font-bold shadow-md border border-white"
                      title="Delete cable"
                    >
                      ×
                    </button>
                  </foreignObject>
                </g>
              );
            })}

            {/* Drawing connection line */}
            {connecting && (() => {
              const fromNode = nodes.find(n => n.id === connecting.nodeId);
              if (!fromNode) return null;
              const fromPos = getPortPosition(fromNode, connecting.portType, connecting.portIndex);
              const midX = (fromPos.x + mousePos.x) / 2;
              const path = `M ${fromPos.x} ${fromPos.y} C ${midX} ${fromPos.y}, ${midX} ${mousePos.y}, ${mousePos.x} ${mousePos.y}`;
              return (
                <path
                  d={path}
                  fill="none"
                  stroke="#9CA3AF"
                  strokeWidth="2"
                  strokeDasharray="5,5"
                />
              );
            })()}
          </svg>

          {/* Nodes */}
          {nodes.map(node => (
            <div
              key={node.id}
              className={`absolute cursor-move select-none transition-all ${
                selectedNode?.id === node.id ? 'z-10' : ''
              }`}
              style={{
                left: node.x,
                top: node.y,
                width: node.width,
                height: node.height,
              }}
              onMouseDown={(e) => handleNodeMouseDown(e, node)}
            >
              {/* OLT - VSOL Style 1U Rack Mount */}
              {node.type === 'olt' && (
                <div className={`relative h-full ${selectedNode?.id === node.id ? 'ring-2 ring-cyan-400 ring-offset-1' : ''}`}>
                  {/* Main chassis - Black metal body */}
                  <div className="absolute inset-0 bg-[#1a1a1a] rounded-sm shadow-xl" style={{boxShadow: '0 4px 12px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1)'}}>
                    {/* Top metal edge */}
                    <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-b from-[#3a3a3a] to-[#1a1a1a]"></div>
                    {/* Bottom metal edge */}
                    <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-gradient-to-t from-[#0a0a0a] to-[#1a1a1a]"></div>

                    {/* Left section - Logo & Status */}
                    <div className="absolute left-1 top-0 bottom-0 w-20 flex flex-col justify-center">
                      {/* VSOL Logo area */}
                      <div className="bg-[#2a2a2a] rounded-sm px-1.5 py-1 mx-0.5">
                        <div className="text-[8px] font-bold text-cyan-400 tracking-wide">VSOL</div>
                        <div className="text-[9px] font-bold text-white truncate">{node.name}</div>
                      </div>
                      {/* Status LEDs row */}
                      <div className="flex gap-1 mt-1 px-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-lg" style={{boxShadow: '0 0 4px #22c55e'}}></div>
                        <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 shadow-lg" style={{boxShadow: '0 0 4px #06b6d4'}}></div>
                        <div className="w-1.5 h-1.5 rounded-full bg-orange-500 shadow-lg" style={{boxShadow: '0 0 4px #f97316'}}></div>
                      </div>
                    </div>

                    {/* PON Ports Section */}
                    <div className="absolute right-1 top-1 bottom-1 flex flex-col justify-around" style={{width: '24px'}}>
                      <div className="text-[5px] text-gray-500 text-center mb-0.5">PON</div>
                      {Array.from({ length: node.ponPorts }, (_, i) => {
                        const power = powerMap[`${node.id}-output-${i}`];
                        return (
                          <div key={i} className="flex items-center justify-end gap-0.5">
                            <span className="text-[5px] text-gray-500">{i + 1}</span>
                            <div
                              className="port w-3 h-2.5 bg-[#0d0d0d] border border-[#3a3a3a] cursor-crosshair hover:border-cyan-400 transition-all flex items-center justify-center"
                              style={{ marginRight: -6, borderRadius: '1px' }}
                              onMouseDown={(e) => handlePortMouseDown(e, node, 'output', i)}
                              onMouseUp={(e) => handlePortMouseUp(e, node, 'output', i)}
                              title={`PON ${i + 1}: ${power?.toFixed(1) || oltPower} dBm`}
                            >
                              <div className="w-1.5 h-1 bg-green-500 rounded-sm" style={{boxShadow: '0 0 3px #22c55e'}}></div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {/* Splitter - Fiber Optic PLC Splitter Box */}
              {node.type === 'splitter' && (
                <div className={`relative h-full ${selectedNode?.id === node.id ? 'ring-2 ring-purple-400 ring-offset-1' : ''}`}>
                  {/* Splitter enclosure */}
                  <div className="absolute inset-0 bg-gradient-to-b from-[#f8f8f8] to-[#e8e8e8] rounded shadow-md border border-[#ccc]" style={{boxShadow: '0 2px 8px rgba(0,0,0,0.15)'}}>
                    {/* Top label strip */}
                    <div className="absolute top-0 left-0 right-0 h-3 bg-gradient-to-b from-[#4a5568] to-[#2d3748] flex items-center justify-center rounded-t">
                      <span className="text-[6px] font-bold text-white tracking-wide">{node.splitterType || node.name}</span>
                    </div>

                    {/* Input fiber entry - Blue SC/APC */}
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center">
                      <div className="w-2 h-4 bg-blue-600 rounded-r-sm border-r border-t border-b border-blue-700" style={{marginLeft: '-2px'}}></div>
                    </div>

                    {/* Center - Splitter info */}
                    <div className="absolute inset-0 flex items-center justify-center pt-3">
                      <div className="text-[5px] text-gray-500 font-medium">{node.category}</div>
                    </div>

                    {/* Output fiber entries - Orange SC/APC */}
                    <div className="absolute right-0 top-3 bottom-1 flex flex-col justify-around">
                      {Array.from({ length: node.outputPorts }, (_, i) => {
                        const power = powerMap[`${node.id}-output-${i}`];
                        const loss = node.portLosses ? node.portLosses[i] : node.loss;
                        return (
                          <div key={i} className="flex items-center">
                            <div
                              className="port w-2 h-2.5 bg-orange-500 rounded-l-sm border-l border-t border-b border-orange-600 cursor-crosshair hover:bg-orange-400 transition-all"
                              style={{ marginRight: -4 }}
                              onMouseDown={(e) => handlePortMouseDown(e, node, 'output', i)}
                              onMouseUp={(e) => handlePortMouseUp(e, node, 'output', i)}
                              title={`Port ${i + 1}: ${power?.toFixed(1) || '?'} dBm (${loss} dB loss)`}
                            />
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Input port hitbox */}
                  <div
                    className="port absolute left-0 top-1/2 -translate-y-1/2 w-3 h-5 cursor-crosshair opacity-0"
                    style={{ marginLeft: -6 }}
                    onMouseDown={(e) => handlePortMouseDown(e, node, 'input', 0)}
                    onMouseUp={(e) => handlePortMouseUp(e, node, 'input', 0)}
                    title={`Input: ${powerMap[`${node.id}-input`]?.toFixed(1) || '?'} dBm`}
                  />
                </div>
              )}

              {/* ONU - VSOL Style CPE Device */}
              {node.type === 'onu' && (
                <div className={`relative h-full ${selectedNode?.id === node.id ? 'ring-2 ring-green-400 ring-offset-1' : ''}`}>
                  {/* ONU body - White plastic casing */}
                  <div className="absolute inset-0 bg-gradient-to-b from-[#fefefe] to-[#f0f0f0] rounded shadow-md border border-[#ddd]" style={{boxShadow: '0 2px 6px rgba(0,0,0,0.1)'}}>
                    {/* Top brand strip */}
                    <div className="absolute top-0 left-0 right-0 h-3 bg-gradient-to-r from-[#1e3a5f] via-[#2563eb] to-[#1e3a5f] rounded-t flex items-center px-1.5">
                      <span className="text-[7px] font-bold text-white">ONU</span>
                    </div>

                    {/* Status LEDs */}
                    <div className="absolute top-4 right-1.5 flex gap-1">
                      <div className={`w-1.5 h-1.5 rounded-full ${powerMap[`${node.id}-rx`] !== undefined ? 'bg-green-500' : 'bg-gray-300'}`} style={powerMap[`${node.id}-rx`] !== undefined ? {boxShadow: '0 0 4px #22c55e'} : {}}></div>
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-500" style={{boxShadow: '0 0 4px #3b82f6'}}></div>
                    </div>

                    {/* Device name */}
                    <div className="absolute top-4 left-1.5 right-6">
                      <div className="text-[8px] font-medium text-gray-700 truncate">{node.name}</div>
                    </div>

                    {/* Power level indicator - BIGGER */}
                    {powerMap[`${node.id}-rx`] !== undefined && (
                      <div className="absolute bottom-1 left-1 right-1">
                        <div className={`text-[10px] text-center font-bold py-1 rounded ${
                          getPowerStatus(powerMap[`${node.id}-rx`]).status === 'GOOD' ? 'bg-green-500 text-white' :
                          getPowerStatus(powerMap[`${node.id}-rx`]).status === 'MARGINAL' ? 'bg-yellow-500 text-white' :
                          'bg-red-500 text-white'
                        }`} style={{textShadow: '0 1px 2px rgba(0,0,0,0.3)'}}>
                          {powerMap[`${node.id}-rx`].toFixed(1)} dBm
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Fiber input port - Green SC connector - VISIBLE & CLICKABLE */}
                  <div
                    className="port absolute left-0 top-1/2 -translate-y-1/2 w-3 h-5 bg-green-600 rounded-r-sm border-r border-t border-b border-green-700 cursor-crosshair hover:bg-green-500 hover:scale-110 transition-all"
                    style={{ marginLeft: -6 }}
                    onMouseDown={(e) => handlePortMouseDown(e, node, 'input', 0)}
                    onMouseUp={(e) => handlePortMouseUp(e, node, 'input', 0)}
                    title={`RX: ${powerMap[`${node.id}-rx`]?.toFixed(1) || '?'} dBm`}
                  />

                  {/* Ethernet output port - Yellow RJ45 - for connecting to switch */}
                  <div
                    className="port absolute right-0 top-1/2 -translate-y-1/2 w-3 h-4 bg-yellow-500 rounded-l-sm border-l border-t border-b border-yellow-600 cursor-crosshair hover:bg-yellow-400 hover:scale-110 transition-all"
                    style={{ marginRight: -6 }}
                    onMouseDown={(e) => handlePortMouseDown(e, node, 'output', 0)}
                    onMouseUp={(e) => handlePortMouseUp(e, node, 'output', 0)}
                    title="Ethernet output (to Switch)"
                  />
                </div>
              )}

              {/* Switch - Layer 2 Network Switch with multiple ports */}
              {node.type === 'switch' && (
                <div className={`relative h-full ${selectedNode?.id === node.id ? 'ring-2 ring-orange-400 ring-offset-1' : ''}`}>
                  {/* Switch body - Dark metal casing */}
                  <div className="absolute inset-0 bg-gradient-to-b from-[#2a2a2a] to-[#1a1a1a] rounded-lg shadow-lg border border-[#3a3a3a]" style={{boxShadow: '0 3px 10px rgba(0,0,0,0.4)'}}>
                    {/* Top label strip */}
                    <div className="absolute top-0 left-0 right-0 h-6 bg-gradient-to-r from-orange-600 via-orange-500 to-orange-600 rounded-t-lg flex items-center justify-between px-2">
                      <span className="text-[8px] font-bold text-white">L2 SWITCH</span>
                      <span className="text-[8px] font-bold text-orange-200">{node.ports} PORT</span>
                    </div>

                    {/* Switch name - clickable */}
                    <div
                      className="absolute top-7 left-1 right-1 cursor-pointer"
                      onClick={(e) => {
                        e.stopPropagation();
                        const newName = prompt('Switch name:', node.name || '');
                        if (newName !== null && newName.trim()) {
                          updateNode(node.id, 'name', newName.trim());
                        }
                      }}
                      title="Click to rename switch"
                    >
                      <div className="text-[9px] font-bold text-white truncate text-center bg-gray-700/50 rounded px-1 py-0.5">{node.name}</div>
                    </div>

                    {/* Port rows - each port with number */}
                    <div className="absolute top-14 left-1 right-1 bottom-1">
                      {Array.from({ length: node.ports }, (_, i) => (
                        <div key={i} className="flex items-center h-[22px] border-b border-gray-700 last:border-b-0">
                          <div className="w-6 text-[9px] font-bold text-orange-400 text-center">{i + 1}</div>
                          <div className="flex-1 h-3 bg-gray-700 rounded mx-1">
                            <div className="h-full w-1/3 bg-green-500 rounded" style={{boxShadow: '0 0 3px #22c55e'}}></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Input port (from ONU) - Yellow RJ45 - at top left */}
                  <div
                    className="port absolute left-0 w-4 h-5 bg-yellow-500 rounded-r-sm border-r border-t border-b border-yellow-600 cursor-crosshair hover:bg-yellow-400 hover:scale-110 transition-all"
                    style={{ marginLeft: -8, top: 12 }}
                    onMouseDown={(e) => handlePortMouseDown(e, node, 'input', 0)}
                    onMouseUp={(e) => handlePortMouseUp(e, node, 'input', 0)}
                    title="Uplink (from ONU)"
                  />

                  {/* Output ports (to Building floors) - Blue RJ45 - one for each port */}
                  {Array.from({ length: node.ports }, (_, i) => (
                    <div
                      key={i}
                      className="port absolute right-0 w-4 h-4 bg-blue-500 rounded-l-sm border-l border-t border-b border-blue-600 cursor-crosshair hover:bg-blue-400 hover:scale-110 transition-all flex items-center justify-center"
                      style={{ marginRight: -8, top: 30 + i * 22 + 5 }}
                      onMouseDown={(e) => handlePortMouseDown(e, node, 'output', i)}
                      onMouseUp={(e) => handlePortMouseUp(e, node, 'output', i)}
                      title={`Port ${i + 1} → Floor`}
                    >
                      <span className="text-[6px] font-bold text-white">{i + 1}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Building with floors and 2 homes per floor */}
              {node.type === 'building' && (
                <div className={`relative h-full ${selectedNode?.id === node.id ? 'ring-2 ring-indigo-400 ring-offset-1' : ''}`}>
                  {/* Building body */}
                  <div className="absolute inset-0 bg-gradient-to-b from-[#4a5568] to-[#2d3748] rounded-lg shadow-lg border-2 border-gray-600" style={{boxShadow: '0 4px 15px rgba(0,0,0,0.4)'}}>
                    {/* Roof */}
                    <div className="absolute -top-2 left-2 right-2 h-3 bg-gradient-to-b from-[#718096] to-[#4a5568] rounded-t-lg border-t-2 border-l-2 border-r-2 border-gray-500"></div>

                    {/* Building name header - clickable to edit */}
                    <div className="absolute top-1 left-0 right-0 flex items-center justify-center">
                      <div
                        className="px-2 py-0.5 bg-indigo-600 rounded text-[10px] font-bold text-white shadow cursor-pointer hover:bg-indigo-500 transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          const newName = prompt('Building name:', node.name || '');
                          if (newName !== null && newName.trim()) {
                            updateNode(node.id, 'name', newName.trim());
                          }
                        }}
                        title="Click to change building name"
                      >
                        {node.name}
                      </div>
                    </div>

                    {/* Floors container */}
                    <div className="absolute top-7 left-1 right-1 bottom-6 overflow-hidden rounded">
                      {/* Render floors from top to bottom */}
                      {Array.from({ length: node.totalFloors || 12 }, (_, i) => (node.totalFloors || 12) - i).map(floorNum => {
                        const defaultFloor = { home1: { customer: '', unit: `${floorNum}A` }, home2: { customer: '', unit: `${floorNum}B` } };
                        const floorData = node.floors?.[floorNum] || defaultFloor;
                        const home1 = floorData.home1 || { customer: '', unit: `${floorNum}A` };
                        const home2 = floorData.home2 || { customer: '', unit: `${floorNum}B` };
                        return (
                          <div key={floorNum} className="flex h-[24px] border-b border-gray-600 last:border-b-0">
                            {/* Floor number - bigger */}
                            <div className="w-7 bg-gray-700 flex items-center justify-center border-r border-gray-600">
                              <span className="text-[10px] font-bold text-yellow-300">{floorNum}</span>
                            </div>
                            {/* Home 1 */}
                            <div
                              className="flex-1 bg-gradient-to-b from-amber-100 to-amber-200 border-r border-gray-500 flex flex-col items-center justify-center cursor-pointer hover:from-amber-200 hover:to-amber-300 transition-colors"
                              onClick={(e) => {
                                e.stopPropagation();
                                const newName = prompt(`Customer name for ${home1.unit || `${floorNum}A`}:`, home1.customer || '');
                                if (newName !== null) {
                                  const newFloors = { ...(node.floors || {}) };
                                  newFloors[floorNum] = {
                                    home1: { customer: newName, unit: home1.unit || `${floorNum}A` },
                                    home2: home2
                                  };
                                  updateNode(node.id, 'floors', newFloors);
                                }
                              }}
                              title={`${home1.unit || `${floorNum}A`}: ${home1.customer || 'Click to add customer'}`}
                            >
                              <div className="text-[7px] font-bold text-gray-700">{home1.unit || `${floorNum}A`}</div>
                              <div className="text-[6px] text-gray-600 truncate w-full px-0.5 text-center">
                                {home1.customer || '---'}
                              </div>
                            </div>
                            {/* Home 2 */}
                            <div
                              className="flex-1 bg-gradient-to-b from-blue-100 to-blue-200 flex flex-col items-center justify-center cursor-pointer hover:from-blue-200 hover:to-blue-300 transition-colors"
                              onClick={(e) => {
                                e.stopPropagation();
                                const newName = prompt(`Customer name for ${home2.unit || `${floorNum}B`}:`, home2.customer || '');
                                if (newName !== null) {
                                  const newFloors = { ...(node.floors || {}) };
                                  newFloors[floorNum] = {
                                    home1: home1,
                                    home2: { customer: newName, unit: home2.unit || `${floorNum}B` }
                                  };
                                  updateNode(node.id, 'floors', newFloors);
                                }
                              }}
                              title={`${home2.unit || `${floorNum}B`}: ${home2.customer || 'Click to add customer'}`}
                            >
                              <div className="text-[7px] font-bold text-gray-700">{home2.unit || `${floorNum}B`}</div>
                              <div className="text-[6px] text-gray-600 truncate w-full px-0.5 text-center">
                                {home2.customer || '---'}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Add/Remove floor buttons at bottom */}
                    <div className="absolute bottom-1 left-1 right-1 flex justify-center gap-1">
                      <button
                        className="px-2 py-0.5 bg-red-500 hover:bg-red-600 text-white text-[9px] font-bold rounded shadow transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          const currentFloors = node.totalFloors || 12;
                          if (currentFloors > 1) {
                            const newTotal = currentFloors - 1;
                            const newFloors = { ...(node.floors || {}) };
                            delete newFloors[currentFloors]; // Remove top floor
                            updateNode(node.id, 'totalFloors', newTotal);
                            updateNode(node.id, 'floors', newFloors);
                            updateNode(node.id, 'height', 50 + newTotal * 24);
                          }
                        }}
                        title="Remove top floor"
                      >
                        − Floor
                      </button>
                      <button
                        className="px-2 py-0.5 bg-green-500 hover:bg-green-600 text-white text-[9px] font-bold rounded shadow transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          const currentFloors = node.totalFloors || 12;
                          const newTotal = currentFloors + 1;
                          const newFloors = { ...(node.floors || {}) };
                          newFloors[newTotal] = {
                            home1: { customer: '', unit: `${newTotal}A` },
                            home2: { customer: '', unit: `${newTotal}B` }
                          };
                          updateNode(node.id, 'totalFloors', newTotal);
                          updateNode(node.id, 'floors', newFloors);
                          updateNode(node.id, 'height', 50 + newTotal * 24);
                        }}
                        title="Add new floor"
                      >
                        + Floor
                      </button>
                    </div>
                  </div>

                  {/* Input ports for each floor (from Switch) - Blue RJ45 */}
                  {Array.from({ length: node.totalFloors || 12 }, (_, i) => {
                    const floorNum = (node.totalFloors || 12) - i; // Top floor first
                    const floorHeight = 24;
                    return (
                      <div
                        key={floorNum}
                        className="port absolute left-0 w-4 h-4 bg-blue-500 rounded-r-sm border-r border-t border-b border-blue-600 cursor-crosshair hover:bg-blue-400 hover:scale-110 transition-all flex items-center justify-center"
                        style={{ marginLeft: -8, top: 30 + i * floorHeight + 4 }}
                        onMouseDown={(e) => handlePortMouseDown(e, node, 'input', floorNum)}
                        onMouseUp={(e) => handlePortMouseUp(e, node, 'input', floorNum)}
                        title={`Floor ${floorNum} input`}
                      >
                        <span className="text-[5px] font-bold text-white">{floorNum}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ))}

          {/* Instructions overlay when empty */}
          {nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center text-gray-400">
                <svg className="w-16 h-16 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                <p className="text-lg">Click buttons above to add components</p>
                <p className="text-sm mt-2">Drag ports to connect them with fiber cables</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Properties Panel */}
      {selectedNode && selectedNode.type !== 'connection' && (
        <div className="bg-white rounded-xl shadow-md p-4">
          <h3 className="font-bold text-gray-800 mb-3">Properties: {selectedNode.name}</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Name</label>
              <input
                type="text"
                value={selectedNode.name}
                onChange={(e) => updateNode(selectedNode.id, 'name', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
            </div>
            {selectedNode.type === 'splitter' && (
              <>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Type</label>
                  <select
                    value={selectedNode.splitterType}
                    onChange={(e) => {
                      const newType = e.target.value;
                      const def = splitterTypes[newType];
                      updateNode(selectedNode.id, 'splitterType', newType);
                      updateNode(selectedNode.id, 'name', newType);
                      updateNode(selectedNode.id, 'outputPorts', def.ports);
                      updateNode(selectedNode.id, 'loss', def.loss);
                      updateNode(selectedNode.id, 'portLosses', def.portLosses);
                      updateNode(selectedNode.id, 'height', 35 + def.ports * 10);
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  >
                    {Object.keys(splitterTypes).map(t => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Brand</label>
                  <input
                    type="text"
                    value={selectedNode.brand || 'Generic'}
                    onChange={(e) => updateNode(selectedNode.id, 'brand', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  />
                </div>
              </>
            )}
            {selectedNode.type === 'onu' && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">Distance (m)</label>
                <input
                  type="number"
                  value={selectedNode.distance || 500}
                  onChange={(e) => updateNode(selectedNode.id, 'distance', parseInt(e.target.value) || 500)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
            )}
            {selectedNode.type === 'switch' && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">Ports</label>
                <select
                  value={selectedNode.ports}
                  onChange={(e) => updateNode(selectedNode.id, 'ports', parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value={8}>8 Ports</option>
                  <option value={16}>16 Ports</option>
                  <option value={24}>24 Ports</option>
                  <option value={48}>48 Ports</option>
                </select>
              </div>
            )}
            {selectedNode.type === 'building' && (
              <>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Total Floors</label>
                  <select
                    value={selectedNode.totalFloors || 12}
                    onChange={(e) => {
                      const newTotal = parseInt(e.target.value);
                      const newFloors = {};
                      for (let f = 1; f <= newTotal; f++) {
                        newFloors[f] = selectedNode.floors?.[f] || {
                          home1: { customer: '', unit: `${f}A` },
                          home2: { customer: '', unit: `${f}B` },
                        };
                      }
                      updateNode(selectedNode.id, 'totalFloors', newTotal);
                      updateNode(selectedNode.id, 'floors', newFloors);
                      updateNode(selectedNode.id, 'height', 30 + newTotal * 24);
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  >
                    {[4, 6, 8, 10, 12, 14, 16, 18, 20].map(n => (
                      <option key={n} value={n}>{n} Floors</option>
                    ))}
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-xs text-gray-500 mb-1">
                    Click on any home in the building to set customer name
                  </label>
                  <div className="text-xs text-indigo-600 font-medium">
                    {Object.values(selectedNode.floors || {}).reduce((count, floor) => {
                      return count + (floor.home1?.customer ? 1 : 0) + (floor.home2?.customer ? 1 : 0);
                    }, 0)} / {(selectedNode.totalFloors || 12) * 2} homes assigned
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Connection Properties */}
      {selectedNode && selectedNode.type === 'connection' && (
        <div className="bg-white rounded-xl shadow-md p-4 border-2 border-blue-500">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-gray-800 flex items-center gap-2">
              <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101" />
              </svg>
              Cable Properties
            </h3>
            <button
              onClick={() => { deleteConnection(selectedNode.id); setSelectedNode(null); }}
              className="px-3 py-1.5 bg-red-500 text-white rounded-lg hover:bg-red-600 text-sm flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete Cable
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-1 font-medium">Cable Length (meters)</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={selectedNode.cableLength || 500}
                  onChange={(e) => updateConnection(selectedNode.id, 'cableLength', parseInt(e.target.value) || 100)}
                  className="w-full px-3 py-2 border-2 border-blue-300 rounded-lg text-sm font-bold focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
                  step="50"
                  min="0"
                />
                <span className="text-gray-500 text-sm">m</span>
              </div>
              <div className="flex gap-1 mt-2">
                {[50, 100, 200, 500, 1000, 2000].map(len => (
                  <button
                    key={len}
                    onClick={() => updateConnection(selectedNode.id, 'cableLength', len)}
                    className={`px-2 py-1 text-xs rounded ${selectedNode.cableLength === len ? 'bg-blue-500 text-white' : 'bg-gray-100 hover:bg-gray-200 text-gray-600'}`}
                  >
                    {len}m
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Connectors</label>
              <input
                type="number"
                value={selectedNode.connectors || 2}
                onChange={(e) => updateConnection(selectedNode.id, 'connectors', parseInt(e.target.value) || 2)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                min="0"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Fiber Loss</label>
              <p className="text-lg font-bold text-orange-600">
                {(((selectedNode.cableLength || 500) / 1000) * fiberLossPerKm).toFixed(2)} dB
              </p>
              <p className="text-xs text-gray-400">{((selectedNode.cableLength || 500) / 1000).toFixed(2)} km × 0.35</p>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Total Loss</label>
              <p className="text-lg font-bold text-red-600">
                {(((selectedNode.cableLength || 500) / 1000) * fiberLossPerKm + (selectedNode.connectors || 2) * connectorLoss).toFixed(2)} dB
              </p>
              <p className="text-xs text-gray-400">fiber + {selectedNode.connectors || 2} conn</p>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
function Sidebar({ currentPage, onNavigate, user, onLogout, isOpen, onClose, pageName }) {
  const isAdmin = user?.role === 'admin';

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
    { id: 'onus', label: 'ONUs', icon: 'M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z' },
    { id: 'regions', label: 'Regions', icon: 'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z', adminOnly: false },
    { id: 'splitter', label: 'Splitter Simulator', icon: 'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1' },
  ];

  if (isAdmin) {
    menuItems.push({ id: 'users', label: 'Users', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' });
  }

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 bg-black/30 z-40 lg:hidden transition-opacity" onClick={onClose} />
      )}
      <aside className={`fixed inset-y-0 left-0 z-50 w-[280px] bg-white border-r border-[#e8eaed] transform transition-all duration-300 ease-material lg:translate-x-0 lg:static lg:inset-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex flex-col h-full">
          {/* Logo Section */}
          <div className="p-6 border-b border-[#e8eaed]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#2563eb] rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
                  </svg>
                </div>
                <div>
                  <h1 className="text-base font-semibold text-[#111827]">{pageName || 'OLT Manager'}</h1>
                  <p className="text-xs text-[#9ca3af]">GPON Network</p>
                </div>
              </div>
              <button onClick={onClose} aria-label="Close menu" title="Close menu" className="lg:hidden p-2 text-[#9ca3af] hover:text-[#111827] hover:bg-[#f4f5f7] rounded-lg transition-colors">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
            <p className="px-3 py-2 text-xs font-medium text-[#9ca3af] uppercase tracking-wider">Menu</p>
            {menuItems.map((item) => (
              <button
                key={item.id}
                onClick={() => { onNavigate(item.id); onClose(); }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 ${
                  currentPage === item.id
                    ? 'bg-blue-50 text-[#2563eb]'
                    : 'text-[#4b5563] hover:bg-[#f4f5f7] hover:text-[#111827]'
                }`}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                </svg>
                <span className="font-medium text-sm">{item.label}</span>
              </button>
            ))}
          </nav>

          {/* User Profile Section */}
          <div className="p-4 border-t border-[#e8eaed]">
            <div className="flex items-center gap-3 mb-3">
              <div className="relative">
                <div className="w-10 h-10 bg-[#2563eb] rounded-lg flex items-center justify-center text-white font-semibold text-sm">
                  {user?.username?.[0]?.toUpperCase() || 'U'}
                </div>
                <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-[#059669] rounded-full border-2 border-white"></div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[#111827] truncate">{user?.full_name || user?.username}</p>
                <p className="text-xs text-[#9ca3af] capitalize">{user?.role}</p>
              </div>
            </div>
            <button
              onClick={onLogout}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 text-[#4b5563] hover:text-[#dc2626] hover:bg-red-50 rounded-lg transition-all duration-150 border border-[#e8eaed]"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              <span className="text-sm font-medium">Sign Out</span>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

// Dashboard Component
function Dashboard({ user, onLogout, pageName }) {
  // Load saved page from localStorage, default to dashboard
  const [currentPage, setCurrentPage] = useState(() => {
    const savedPage = localStorage.getItem('currentPage');
    return savedPage || 'dashboard';
  });

  // Save current page to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('currentPage', currentPage);
  }, [currentPage]);
  const [stats, setStats] = useState(null);
  const [olts, setOLTs] = useState([]);
  const [onus, setONUs] = useState([]);
  const [regions, setRegions] = useState([]);
  const [users, setUsers] = useState([]);
  const [settings, setSettings] = useState(null);
  const [selectedOLT, setSelectedOLT] = useState(null);
  const [selectedRegion, setSelectedRegion] = useState(null);
  const [selectedPonPort, setSelectedPonPort] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [showAddOLTModal, setShowAddOLTModal] = useState(false);
  const [showEditONUModal, setShowEditONUModal] = useState(false);
  const [showRegionModal, setShowRegionModal] = useState(false);
  const [showUserModal, setShowUserModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showTrafficGraphModal, setShowTrafficGraphModal] = useState(false);
  const [graphEntity, setGraphEntity] = useState({ type: null, id: null, name: '' });
  const [editingONU, setEditingONU] = useState(null);
  const [editingRegion, setEditingRegion] = useState(null);
  const [editingUser, setEditingUser] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [mobilePreviewImages, setMobilePreviewImages] = useState(null);
  const [mobilePreviewTitle, setMobilePreviewTitle] = useState('');
  const [trafficData, setTrafficData] = useState(null);
  const [trafficLoading, setTrafficLoading] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);
  const trafficBufferRef = useRef({});  // Buffer to keep traffic values between updates

  const isAdmin = user?.role === 'admin';

  const handleMobileImagePreview = (onu) => {
    const images = onu.image_urls || (onu.image_url ? [onu.image_url] : []);
    if (images.length > 0) {
      setMobilePreviewImages(images);
      setMobilePreviewTitle(onu.description || `ONU ${onu.pon_port}:${onu.onu_id}`);
    }
  };

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Fetch data functions
  const fetchStats = useCallback(async () => {
    try {
      const response = await api.getDashboardStats();
      setStats(response.data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  }, []);

  const fetchOLTs = useCallback(async () => {
    try {
      const response = await api.getOLTs();
      setOLTs(response.data.olts);
    } catch (error) {
      console.error('Failed to fetch OLTs:', error);
    }
  }, []);

  const fetchONUs = useCallback(async () => {
    try {
      let response;
      const params = {};
      if (searchQuery) {
        response = await api.searchONUs(searchQuery);
      } else {
        if (selectedOLT) params.olt_id = selectedOLT;
        if (selectedRegion) params.region_id = selectedRegion;
        response = await api.getONUs(params);
      }
      setONUs(response.data.onus);
    } catch (error) {
      console.error('Failed to fetch ONUs:', error);
    }
  }, [selectedOLT, selectedRegion, searchQuery]);

  const fetchRegions = useCallback(async () => {
    try {
      const response = await api.getRegions();
      setRegions(response.data.regions || response.data);
    } catch (error) {
      console.error('Failed to fetch regions:', error);
    }
  }, []);

  const fetchUsers = useCallback(async () => {
    if (!isAdmin) return;
    try {
      const response = await api.getUsers();
      setUsers(response.data.users || response.data);
    } catch (error) {
      console.error('Failed to fetch users:', error);
    }
  }, [isAdmin]);

  const fetchSettings = useCallback(async () => {
    try {
      const response = await api.getSettings();
      setSettings(response.data);
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    }
  }, []);

  // WebSocket connection for live traffic
  const connectWebSocket = useCallback((oltId) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    // Construct WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const apiUrl = process.env.REACT_APP_API_URL || '';
    let wsHost = window.location.host;

    if (apiUrl) {
      // Extract host from API URL
      try {
        const url = new URL(apiUrl);
        wsHost = url.host;
      } catch (e) {
        console.error('Invalid API URL:', apiUrl);
      }
    }

    const wsUrl = `${protocol}//${wsHost}/ws/traffic/${oltId}`;
    console.log('Connecting to WebSocket:', wsUrl);

    // Clear buffer when connecting to new OLT
    trafficBufferRef.current = {};
    setTrafficLoading(true);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected for OLT', oltId);
      setWsConnected(true);
      setTrafficLoading(false);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // If we have new traffic data, merge it with the buffer
        if (data.traffic && data.traffic.length > 0) {
          // Update buffer with new values
          data.traffic.forEach(t => {
            trafficBufferRef.current[t.mac_address] = {
              ...t,
              lastUpdate: Date.now()
            };
          });

          // Create merged traffic array from buffer (keeps old values visible)
          const mergedTraffic = Object.values(trafficBufferRef.current)
            .filter(t => Date.now() - t.lastUpdate < 30000)  // Remove entries older than 30 seconds
            .sort((a, b) => (b.rx_kbps + b.tx_kbps) - (a.rx_kbps + a.tx_kbps));

          setTrafficData({
            ...data,
            traffic: mergedTraffic
          });
        } else {
          // No new traffic, but keep showing buffer data
          const bufferedTraffic = Object.values(trafficBufferRef.current)
            .filter(t => Date.now() - t.lastUpdate < 30000)
            .sort((a, b) => (b.rx_kbps + b.tx_kbps) - (a.rx_kbps + a.tx_kbps));

          setTrafficData({
            ...data,
            traffic: bufferedTraffic
          });
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setWsConnected(false);
      setTrafficLoading(false);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setWsConnected(false);
    };

    wsRef.current = ws;
  }, []);

  // Connect/disconnect WebSocket when OLT is selected on ONUs page
  useEffect(() => {
    if (currentPage !== 'onus' || !selectedOLT) {
      // Close WebSocket if not on ONUs page or no OLT selected
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setTrafficData(null);
      setWsConnected(false);
      trafficBufferRef.current = {};  // Clear buffer
      return;
    }

    // Connect WebSocket for the selected OLT
    connectWebSocket(selectedOLT);

    // Cleanup on unmount or OLT change
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [currentPage, selectedOLT, connectWebSocket]);

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchStats(), fetchOLTs(), fetchONUs(), fetchRegions(), fetchUsers(), fetchSettings()]);
      setLoading(false);
    };
    loadData();
  }, [fetchStats, fetchOLTs, fetchONUs, fetchRegions, fetchUsers, fetchSettings]);

  // Refresh data periodically
  useEffect(() => {
    const interval = setInterval(() => {
      fetchStats();
      fetchOLTs();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchStats, fetchOLTs]);

  // Fetch ONUs when filters change
  useEffect(() => {
    fetchONUs();
  }, [fetchONUs]);

  // Handlers
  const handleSelectOLT = (oltId) => {
    setSelectedOLT(selectedOLT === oltId ? null : oltId);
    setSelectedRegion(null);
    setSelectedPonPort(null);
    setSearchQuery('');
  };

  const handleSelectRegion = (regionId) => {
    setSelectedRegion(regionId);
    setSelectedOLT(null);
    setSearchQuery('');
    if (regionId) setCurrentPage('onus');
  };

  const handleSearch = (e) => {
    e.preventDefault();
    fetchONUs();
  };

  const handleAddOLT = async (data) => {
    await api.createOLT(data);
    await fetchOLTs();
    await fetchStats();
  };

  const handlePollOLT = async (id) => {
    await api.pollOLT(id);
    await fetchOLTs();
    await fetchONUs();
    await fetchStats();
  };

  const handleDeleteOLT = async (id) => {
    await api.deleteOLT(id);
    if (selectedOLT === id) setSelectedOLT(null);
    await fetchOLTs();
    await fetchONUs();
    await fetchStats();
  };

  const handleEditONU = (onu) => {
    setEditingONU(onu);
    setShowEditONUModal(true);
  };

  const handleUpdateONU = async (id, data) => {
    await api.updateONU(id, data);
    await fetchONUs();
  };

  const handleDeleteONU = async (id) => {
    await api.deleteONU(id);
    await fetchONUs();
    await fetchStats();
  };

  const handleOpenGraph = (type, id, name) => {
    setGraphEntity({ type, id, name });
    setShowTrafficGraphModal(true);
  };

  const handleUploadONUImage = async (id, file) => {
    const response = await api.uploadONUImage(id, file);
    await fetchONUs();
    return response.data;
  };

  const handleDeleteONUImage = async (id, imageIndex) => {
    const response = await api.deleteONUImage(id, imageIndex);
    await fetchONUs();
    return response.data;
  };

  const handleSaveRegion = async (data, id) => {
    if (id) {
      await api.updateRegion(id, data);
    } else {
      await api.createRegion(data);
    }
    await fetchRegions();
  };

  const handleDeleteRegion = async (id) => {
    if (window.confirm('Delete this region?')) {
      await api.deleteRegion(id);
      await fetchRegions();
    }
  };

  const handleSaveUser = async (data, id) => {
    if (id) {
      await api.updateUser(id, data);
    } else {
      await api.createUser(data);
    }
    await fetchUsers();
  };

  const handleDeleteUser = async (id) => {
    if (window.confirm('Delete this user?')) {
      await api.deleteUser(id);
      await fetchUsers();
    }
  };

  const handleSaveSettings = async (data) => {
    await api.updateSettings(data);
    await fetchSettings();
  };

  const handleChangePassword = async (data) => {
    await api.changePassword(data);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    onLogout();
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-gray-100 to-gray-50 flex">
      <Sidebar
        currentPage={currentPage}
        onNavigate={setCurrentPage}
        user={user}
        onLogout={handleLogout}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        pageName={pageName}
      />

      <div className="flex-1 flex flex-col min-h-screen bg-[#fafbfc]">
        {/* Header - Compact */}
        <header className="bg-white sticky top-0 z-30 border-b border-[#e8eaed]">
          <div className="flex items-center justify-between px-3 lg:px-4 py-1.5">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden p-1.5 text-[#4b5563] hover:text-[#2563eb] hover:bg-blue-50 rounded-lg transition-all duration-150"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <h1 className="text-sm lg:text-base font-semibold text-[#111827]">
                {pageName || 'OLT Manager'}
              </h1>
            </div>
            <div className="flex items-center gap-2">
              <div className="hidden sm:flex items-center gap-1 px-2 py-0.5 bg-[#d1fae5] rounded-full">
                <span className="w-1.5 h-1.5 bg-[#059669] rounded-full animate-pulse"></span>
                <span className="text-xs font-medium text-[#059669]">Live</span>
              </div>
              <button
                onClick={() => setShowSettingsModal(true)}
                className="p-1.5 text-[#4b5563] hover:text-[#2563eb] hover:bg-blue-50 rounded-lg transition-all duration-150"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </button>
            </div>
          </div>
        </header>

        <main className="flex-1 p-2 lg:p-4">
          {/* Dashboard Page */}
          {currentPage === 'dashboard' && (
            <>
              {/* Stats Cards */}
              {stats && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-4 mb-6">
                  <StatsCard title="Total OLTs" value={stats.total_olts} subValue={`${stats.online_olts} online`} color="blue" icon="olt" />
                  <StatsCard title="Online OLTs" value={stats.online_olts} color="green" icon="online" />
                  <StatsCard title="Total ONUs" value={stats.total_onus} subValue={`${stats.online_onus} online`} color="purple" icon="onu" />
                  <StatsCard title="Offline ONUs" value={stats.offline_onus} color="red" icon="offline" />
                </div>
              )}

              {/* Regions Overview - Enterprise Pro */}
              {regions.length > 0 && (
                <div className="mb-6">
                  <h2 className="text-base font-semibold text-[#111827] mb-4">Regions</h2>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                    {regions.map((region) => (
                      <button
                        key={region.id}
                        onClick={() => handleSelectRegion(region.id)}
                        className="bg-white rounded-xl p-4 text-left hover:shadow-sm transition-all duration-200 border border-[#e8eaed]"
                      >
                        <div className="flex items-center">
                          <div
                            className="w-10 h-10 rounded-lg flex items-center justify-center mr-3"
                            style={{ backgroundColor: region.color ? `${region.color}15` : '#6366F115' }}
                          >
                            <svg className="w-5 h-5" style={{ color: region.color || '#6366F1' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                          </div>
                          <div>
                            <p className="font-medium text-[#111827]">{region.name}</p>
                            <p className="text-sm" style={{ color: region.color || '#6366F1' }}>{region.onu_count || 0} ONUs</p>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* OLTs Section */}
              <div className="mb-6">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-base font-semibold text-[#111827]">OLTs</h2>
                  {isAdmin && (
                    <button
                      onClick={() => setShowAddOLTModal(true)}
                      className="px-3 py-1.5 bg-[#2563eb] text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
                    >
                      + Add OLT
                    </button>
                  )}
                </div>
                {olts.length === 0 ? (
                  <div className="bg-white rounded-xl border border-[#e8eaed] p-8 text-center text-[#9ca3af]">
                    No OLTs configured. {isAdmin && 'Add your first OLT to get started.'}
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {olts.map((olt) => (
                      <OLTCard
                        key={olt.id}
                        olt={olt}
                        onSelect={handleSelectOLT}
                        onPoll={handlePollOLT}
                        onDelete={handleDeleteOLT}
                        isSelected={selectedOLT === olt.id}
                        isAdmin={isAdmin}
                        onGraph={handleOpenGraph}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Quick ONU Stats */}
              {selectedOLT && (
                <div>
                  <div className="flex justify-between items-center mb-4">
                    <h2 className="text-lg font-bold text-gray-800">
                      ONUs - {olts.find((o) => o.id === selectedOLT)?.name}
                    </h2>
                    <button
                      onClick={() => setCurrentPage('onus')}
                      className="text-blue-600 hover:text-blue-800 font-medium"
                    >
                      View All &rarr;
                    </button>
                  </div>
                  <div className="text-sm text-gray-600 mb-2">{onus.length} ONUs</div>
                </div>
              )}
            </>
          )}

          {/* ONUs Page */}
          {currentPage === 'onus' && (
            <>
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
                <div>
                  <h2 className="text-lg font-bold text-gray-800">
                    ONUs
                    {selectedOLT && (
                      <span className="text-sm font-normal text-gray-500 ml-2">
                        ({olts.find((o) => o.id === selectedOLT)?.name})
                      </span>
                    )}
                    {selectedRegion && (
                      <span className="text-sm font-normal text-gray-500 ml-2">
                        ({regions.find((r) => r.id === selectedRegion)?.name})
                      </span>
                    )}
                    {selectedPonPort && (
                      <span className="text-sm font-normal text-emerald-600 ml-2">
                        - PON {selectedPonPort}
                      </span>
                    )}
                  </h2>
                  <p className="text-sm text-gray-500">
                    {selectedPonPort ? onus.filter(onu => onu.pon_port === selectedPonPort).length : onus.length} ONUs shown
                    {selectedPonPort && <span className="text-emerald-600"> (filtered by PON {selectedPonPort})</span>}
                  </p>
                </div>
                <form onSubmit={handleSearch} className="flex gap-2 w-full sm:w-auto">
                  <input
                    type="text"
                    placeholder="Search by name or MAC..."
                    className="flex-1 sm:w-64 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  <button type="submit" className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300">
                    Search
                  </button>
                  {(searchQuery || selectedOLT || selectedRegion || selectedPonPort) && (
                    <button
                      type="button"
                      onClick={() => {
                        setSearchQuery('');
                        setSelectedOLT(null);
                        setSelectedRegion(null);
                        setSelectedPonPort(null);
                      }}
                      className="px-4 py-2 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200"
                    >
                      Clear
                    </button>
                  )}
                </form>
              </div>

              {/* Filter by OLT buttons */}
              <div className="flex flex-wrap gap-2 mb-4">
                <button
                  onClick={() => { setSelectedOLT(null); setSelectedRegion(null); setSelectedPonPort(null); }}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                    !selectedOLT && !selectedRegion ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  All
                </button>
                {olts.map((olt) => (
                  <button
                    key={olt.id}
                    onClick={() => handleSelectOLT(olt.id)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                      selectedOLT === olt.id ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                  >
                    {olt.name}
                  </button>
                ))}
              </div>

              {/* Filter by PON Port buttons - shown when OLT is selected */}
              {selectedOLT && (() => {
                const ponPorts = [...new Set(onus.map(onu => onu.pon_port))].sort((a, b) => a - b);
                return ponPorts.length > 1 ? (
                  <div className="flex flex-wrap items-center gap-2 mb-4">
                    <span className="text-sm text-gray-500 font-medium">PON:</span>
                    <button
                      onClick={() => setSelectedPonPort(null)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                        !selectedPonPort ? 'bg-emerald-600 text-white' : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                      }`}
                    >
                      All
                    </button>
                    {ponPorts.map((port) => {
                      const count = onus.filter(onu => onu.pon_port === port).length;
                      const currentOlt = olts.find(o => o.id === selectedOLT);
                      return (
                        <div key={port} className="flex items-center gap-1">
                          <button
                            onClick={() => setSelectedPonPort(selectedPonPort === port ? null : port)}
                            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition flex items-center gap-1.5 ${
                              selectedPonPort === port ? 'bg-emerald-600 text-white' : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                            }`}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                            </svg>
                            PON {port}
                            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                              selectedPonPort === port ? 'bg-white/20' : 'bg-emerald-200'
                            }`}>
                              {count}
                            </span>
                          </button>
                          {/* Graph button for PON port */}
                          <button
                            onClick={() => handleOpenGraph('pon', `${selectedOLT}:${port}`, `${currentOlt?.name || 'OLT'} - PON ${port}`)}
                            className="p-1.5 rounded-lg bg-purple-100 text-purple-600 hover:bg-purple-200 transition"
                            title={`View traffic graph for PON ${port}`}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                            </svg>
                          </button>
                        </div>
                      );
                    })}
                  </div>
                ) : null;
              })()}

              {/* Traffic Status Indicator */}
              {selectedOLT && (
                <div className="mb-4 flex items-center gap-3">
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-cyan-50 to-blue-50 border border-cyan-200 rounded-lg">
                    {trafficLoading ? (
                      <>
                        <svg className="animate-spin h-4 w-4 text-cyan-600" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span className="text-sm text-cyan-700 font-medium">Updating traffic...</span>
                      </>
                    ) : (
                      <>
                        <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}></span>
                        <svg className="w-4 h-4 text-cyan-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                        </svg>
                        <span className="text-sm text-cyan-700 font-medium">Live Traffic</span>
                      </>
                    )}
                    <span className={`text-xs ${wsConnected ? 'text-green-600 font-medium' : 'text-gray-500'}`}>
                      {wsConnected ? (trafficData?.message ? `(${trafficData.message})` : '(Live ~3s)') : '(connecting...)'}
                    </span>
                  </div>
                  {trafficData && trafficData.olt_id === selectedOLT && trafficData.timestamp && (
                    <span className="text-xs text-gray-500">
                      {new Date(trafficData.timestamp).toLocaleTimeString()}
                    </span>
                  )}
                </div>
              )}

              {(() => {
                const filteredOnus = selectedPonPort ? onus.filter(onu => onu.pon_port === selectedPonPort) : onus;
                return isMobile ? (
                  <>
                    <ImagePreviewModal
                      isOpen={!!mobilePreviewImages}
                      onClose={() => setMobilePreviewImages(null)}
                      images={mobilePreviewImages || []}
                      title={mobilePreviewTitle}
                    />
                    <div>
                      {filteredOnus.map((onu) => (
                        <ONUCard key={onu.id} onu={onu} onEdit={handleEditONU} onDelete={handleDeleteONU} isAdmin={isAdmin} onImagePreview={handleMobileImagePreview} />
                      ))}
                    </div>
                  </>
                ) : (
                  <ONUTable onus={filteredOnus} onEdit={handleEditONU} onDelete={handleDeleteONU} isAdmin={isAdmin} trafficData={selectedOLT && trafficData && trafficData.olt_id === selectedOLT ? trafficData : null} onGraph={handleOpenGraph} />
                );
              })()}
            </>
          )}

          {/* Regions Page */}
          {currentPage === 'regions' && (
            <>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-bold text-gray-800">Regions</h2>
                {isAdmin && (
                  <button
                    onClick={() => { setEditingRegion(null); setShowRegionModal(true); }}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
                  >
                    + Add Region
                  </button>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {regions.map((region) => (
                  <div key={region.id} className="bg-white rounded-xl shadow-md p-4 border-l-4" style={{ borderLeftColor: region.color || '#3B82F6' }}>
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-10 h-10 rounded-lg flex items-center justify-center"
                          style={{ backgroundColor: region.color ? `${region.color}20` : '#3B82F620' }}
                        >
                          <svg className="w-5 h-5" style={{ color: region.color || '#3B82F6' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                          </svg>
                        </div>
                        <div>
                          <h3 className="font-bold text-lg text-gray-800">{region.name}</h3>
                          {region.description && <p className="text-sm text-gray-500">{region.description}</p>}
                        </div>
                      </div>
                      {region.latitude && region.longitude && (
                        <button
                          onClick={() => window.open(`https://www.google.com/maps?q=${region.latitude},${region.longitude}`, '_blank')}
                          className="text-green-600 hover:text-green-800"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                          </svg>
                        </button>
                      )}
                    </div>
                    <div className="flex items-center justify-between">
                      <button
                        onClick={() => handleSelectRegion(region.id)}
                        className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                      >
                        View ONUs &rarr;
                      </button>
                      {isAdmin && (
                        <div className="space-x-2">
                          <button
                            onClick={() => { setEditingRegion(region); setShowRegionModal(true); }}
                            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleDeleteRegion(region.id)}
                            className="text-red-600 hover:text-red-800 text-sm font-medium"
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Splitter Simulator Page */}
          {currentPage === 'splitter' && (
            <SplitterSimulator olts={olts} onus={onus} />
          )}

          {/* Users Page (Admin only) */}
          {currentPage === 'users' && isAdmin && (
            <>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-bold text-gray-800">Users</h2>
                <button
                  onClick={() => { setEditingUser(null); setShowUserModal(true); }}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
                >
                  + Add User
                </button>
              </div>
              <div className="bg-white rounded-xl shadow-md overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Username</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Full Name</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Role</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Status</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {users.map((u) => (
                      <tr key={u.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{u.username}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{u.full_name || '-'}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                            u.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
                          }`}>
                            {u.role}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                            u.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                          }`}>
                            {u.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                          <button
                            onClick={() => { setEditingUser(u); setShowUserModal(true); }}
                            className="text-blue-600 hover:text-blue-800 font-medium"
                          >
                            Edit
                          </button>
                          {u.id !== user.id && (
                            <button
                              onClick={() => handleDeleteUser(u.id)}
                              className="text-red-600 hover:text-red-800 font-medium"
                            >
                              Delete
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </main>

        {/* Footer - Material Design */}
        <footer className="bg-gradient-to-r from-gray-900 via-gray-800 to-gray-900 text-gray-400 py-4 text-center border-t border-gray-700">
          <div className="flex items-center justify-center gap-4 text-sm">
            <span className="font-medium text-gray-300">{pageName || 'OLT Manager'}</span>
            <span className="w-1 h-1 bg-gray-600 rounded-full"></span>
            <div className="flex items-center gap-1.5">
              <svg className="w-4 h-4 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Auto-refresh: 30s</span>
            </div>
          </div>
        </footer>
      </div>

      {/* Modals */}
      <AddOLTModal
        isOpen={showAddOLTModal}
        onClose={() => setShowAddOLTModal(false)}
        onSubmit={handleAddOLT}
        regions={regions}
      />
      <EditONUModal
        isOpen={showEditONUModal}
        onClose={() => { setShowEditONUModal(false); setEditingONU(null); }}
        onu={editingONU}
        onSubmit={handleUpdateONU}
        onImageUpload={handleUploadONUImage}
        onImageDelete={handleDeleteONUImage}
        regions={regions}
      />
      <RegionModal
        isOpen={showRegionModal}
        onClose={() => { setShowRegionModal(false); setEditingRegion(null); }}
        region={editingRegion}
        onSubmit={handleSaveRegion}
      />
      <UserModal
        isOpen={showUserModal}
        onClose={() => { setShowUserModal(false); setEditingUser(null); }}
        user={editingUser}
        onSubmit={handleSaveUser}
        olts={olts}
      />
      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        settings={settings}
        onSubmit={handleSaveSettings}
        onChangePassword={handleChangePassword}
      />
      <TrafficGraphModal
        isOpen={showTrafficGraphModal}
        onClose={() => setShowTrafficGraphModal(false)}
        entityType={graphEntity.type}
        entityId={graphEntity.id}
        entityName={graphEntity.name}
      />
    </div>
  );
}

// Main App Component
function App() {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [settings, setSettings] = useState(null);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await api.getSettings();
        setSettings(response.data);
      } catch (error) {
        console.error('Failed to fetch settings:', error);
      }
    };
    fetchSettings();
  }, []);

  const token = localStorage.getItem('token');
  const systemName = settings?.system_name || 'OLT Manager';

  if (!token || !user) {
    return <LoginPage onLogin={setUser} pageName={systemName} />;
  }

  return <Dashboard user={user} onLogout={() => setUser(null)} pageName={systemName} />;
}

export default App;
