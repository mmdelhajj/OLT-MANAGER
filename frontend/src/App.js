import React, { useState, useEffect, useCallback, useRef, createContext, useContext } from 'react';

// Dark Mode Context - globally accessible
const DarkModeContext = createContext(false);
import * as api from './api';

const APP_VERSION = '2.3.0'; // Speedometer Gauge Health Display
console.log('OLT Manager Pro v' + APP_VERSION + ' - Speedometer Health Gauges');

// VSOL OLT Models with PON port counts - Complete List
const VSOL_OLT_MODELS = {
  // ============ GPON OLT Series ============
  // GPON (1 PON) - Single PON Mini OLT
  'V1600GS': 1,
  'V1600GS-F': 1,
  'V1600GS-ZF': 1,
  'V1600GS-O32': 1,  // Built-in 1:32 splitter
  'V1600GS-WB': 1,

  // GPON (2 PON)
  'V1600GT': 2,
  'V1600GT-2F': 2,

  // GPON (4 PON)
  'V1600G0': 4,
  'V1600G0-B': 4,
  'V1600G0-R': 4,
  'V1601G04': 4,
  'V1601E04': 4,  // EPON/GPON Combo

  // GPON (8 PON)
  'V1600G1': 8,
  'V1600G1-B': 8,
  'V1600G1-R': 8,
  'V1600G1-A': 8,
  'V1600G1WEO': 8,
  'V1600G1WEO-B': 8,  // Outdoor IP65

  // GPON (16 PON)
  'V1600G2': 16,
  'V1600G2-B': 16,
  'V1600G2-R': 16,
  'V1600G2-A': 16,

  // ============ EPON OLT Series ============
  // EPON (1 PON)
  'V1600DS': 1,

  // EPON (2 PON)
  'V1600D2': 2,
  'V1600D2-L': 2,
  'V1601E02': 2,
  'V1601E02-DP': 2,

  // EPON (4 PON)
  'V1600D4': 4,
  'V1600D4-L': 4,
  'V1600D4-DP': 4,
  'V1600D-MINI': 4,
  'V1601E04-DP': 4,
  'V1601E04-BT': 4,

  // EPON (8 PON)
  'V1600D8': 8,
  'V1600D8-L': 8,
  'V1600D8-R': 8,

  // EPON (16 PON)
  'V1600D16': 16,
  'V1600D16-L': 16,

  // ============ 10G/XGS-PON OLT Series ============
  // 10G GPON (2 PON)
  'V1600XG02': 2,
  'V1600XG02-W': 2,

  // 10G GPON (4 PON)
  'V1600XG04': 4,

  // 10G GPON/EPON (8 PON)
  'V3600G1': 8,
  'V3600G1-C': 8,
  'V3600D8': 8,

  // 10G GPON (16 PON)
  'V3600G2': 16,

  // ============ Chassis OLT Series ============
  'V5600X2': 32,   // 32 PON Chassis
  'V5600X4': 64,   // 64 PON Chassis
  'V5600X7': 112,  // 112 PON Chassis

  // ============ Combo/Pizza Box OLT ============
  'V1600P1': 1,
  'V1600P2': 2,
  'V1600P4': 4,
  'V1600P8': 8,

  // Other (manual entry)
  'Other': 0,
};

// Helper function to format uptime in seconds to human readable format
const formatUptime = (seconds) => {
  if (!seconds) return '-';
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days > 0) {
    return `${days}d ${hours}h`;
  } else if (hours > 0) {
    return `${hours}h ${mins}m`;
  }
  return `${mins}m`;
};

// Speedometer Gauge Component - Modern Car Dashboard Style
const SpeedometerGauge = ({ value, max, label, unit, icon, colorStops }) => {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  const angle = (percentage / 100) * 180; // 0 to 180 degrees arc

  // Default color stops: green -> yellow -> red
  const defaultColorStops = [
    { offset: 0, color: '#10b981' },    // Green
    { offset: 50, color: '#f59e0b' },   // Yellow
    { offset: 100, color: '#ef4444' }   // Red
  ];
  const stops = colorStops || defaultColorStops;

  // Get current color based on percentage
  const getCurrentColor = (pct) => {
    if (pct <= 50) return stops[0].color;
    if (pct <= 75) return stops[1].color;
    return stops[2].color;
  };

  const currentColor = getCurrentColor(percentage);
  const gradientId = `gauge-gradient-${label.replace(/\s/g, '')}`;

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 120 70" className="w-20 h-12">
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
            {stops.map((stop, i) => (
              <stop key={i} offset={`${stop.offset}%`} stopColor={stop.color} />
            ))}
          </linearGradient>
          {/* Glow filter */}
          <filter id={`glow-${label}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        {/* Background arc (dark) */}
        <path
          d="M 10 60 A 50 50 0 0 1 110 60"
          fill="none"
          stroke="#1f2937"
          strokeWidth="8"
          strokeLinecap="round"
        />

        {/* Colored arc (gradient) */}
        <path
          d="M 10 60 A 50 50 0 0 1 110 60"
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={`${percentage * 1.57} 157`}
          style={{ transition: 'stroke-dasharray 0.3s ease-out' }}
        />

        {/* Tick marks */}
        {[0, 25, 50, 75, 100].map((tick) => {
          const tickAngle = (tick / 100) * 180 - 180;
          const rad = (tickAngle * Math.PI) / 180;
          const x1 = 60 + 42 * Math.cos(rad);
          const y1 = 60 + 42 * Math.sin(rad);
          const x2 = 60 + 48 * Math.cos(rad);
          const y2 = 60 + 48 * Math.sin(rad);
          return (
            <line
              key={tick}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="#4b5563"
              strokeWidth="1.5"
            />
          );
        })}

        {/* Needle */}
        <g style={{
          transform: `rotate(${angle - 180}deg)`,
          transformOrigin: '60px 60px',
          transition: 'transform 0.3s ease-out'
        }}>
          <line
            x1="60" y1="60" x2="60" y2="18"
            stroke={currentColor}
            strokeWidth="2.5"
            strokeLinecap="round"
            filter={`url(#glow-${label})`}
          />
          {/* Needle tip */}
          <circle cx="60" cy="18" r="2" fill={currentColor} />
        </g>

        {/* Center hub */}
        <circle cx="60" cy="60" r="6" fill="#374151" stroke={currentColor} strokeWidth="2" />
        <circle cx="60" cy="60" r="3" fill={currentColor} />
      </svg>

      {/* Value display */}
      <div className="mt-1 text-center">
        <div className="flex items-center justify-center gap-1">
          <span className="text-lg font-bold tabular-nums" style={{ color: currentColor }}>
            {value !== null ? value : '-'}
          </span>
          <span className="text-xs text-gray-400">{unit}</span>
        </div>
        <div className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</div>
      </div>
    </div>
  );
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
  const darkMode = useContext(DarkModeContext);
  const colorConfig = {
    blue: { iconBg: darkMode ? 'bg-blue-900/50' : 'bg-blue-50', iconColor: 'text-blue-500', trendUp: 'text-emerald-500', trendDown: 'text-red-500' },
    green: { iconBg: darkMode ? 'bg-emerald-900/50' : 'bg-emerald-50', iconColor: 'text-emerald-500', trendUp: 'text-emerald-500', trendDown: 'text-red-500' },
    red: { iconBg: darkMode ? 'bg-red-900/50' : 'bg-red-50', iconColor: 'text-red-500', trendUp: 'text-emerald-500', trendDown: 'text-red-500' },
    yellow: { iconBg: darkMode ? 'bg-amber-900/50' : 'bg-amber-50', iconColor: 'text-amber-500', trendUp: 'text-emerald-500', trendDown: 'text-red-500' },
    purple: { iconBg: darkMode ? 'bg-purple-900/50' : 'bg-purple-50', iconColor: 'text-purple-500', trendUp: 'text-emerald-500', trendDown: 'text-red-500' },
    gray: { iconBg: darkMode ? 'bg-gray-700' : 'bg-gray-100', iconColor: darkMode ? 'text-gray-300' : 'text-gray-600', trendUp: 'text-emerald-500', trendDown: 'text-red-500' },
    indigo: { iconBg: darkMode ? 'bg-indigo-900/50' : 'bg-indigo-50', iconColor: 'text-indigo-500', trendUp: 'text-emerald-500', trendDown: 'text-red-500' },
    cyan: { iconBg: darkMode ? 'bg-cyan-900/50' : 'bg-cyan-50', iconColor: 'text-cyan-500', trendUp: 'text-emerald-500', trendDown: 'text-red-500' },
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
    <div className={`rounded-xl p-5 border hover:shadow-sm transition-all duration-200 ${
      darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-[#e8eaed]'
    }`}>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium mb-1 ${darkMode ? 'text-slate-400' : 'text-[#4b5563]'}`}>{title}</p>
          <div className="flex items-baseline gap-2">
            <p className={`text-3xl font-semibold tabular-nums ${darkMode ? 'text-white' : 'text-[#111827]'}`}>{value}</p>
            {trendValue && (
              <span className={`text-sm font-medium ${trend === 'up' ? cfg.trendUp : cfg.trendDown}`}>
                {trend === 'up' ? '+' : ''}{trendValue}
              </span>
            )}
          </div>
          {subValue && (
            <p className={`text-sm mt-1 ${darkMode ? 'text-slate-500' : 'text-[#9ca3af]'}`}>{subValue}</p>
          )}
        </div>
        <div className={`${cfg.iconBg} rounded-lg p-3`}>
          <svg className={`w-6 h-6 ${cfg.iconColor}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {icons[icon] || icons.olt}
          </svg>
        </div>
      </div>
      {footerText && (
        <div className={`mt-4 pt-3 border-t ${darkMode ? 'border-slate-700' : 'border-[#e8eaed]'}`}>
          <p className={`text-xs ${darkMode ? 'text-slate-500' : 'text-[#9ca3af]'}`}>{footerText}</p>
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
  const darkMode = useContext(DarkModeContext);
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
      <div className={`relative rounded-2xl shadow-2xl w-full ${sizes[size]} max-h-[90vh] overflow-hidden transform transition-all animate-slideUp ${darkMode ? 'bg-slate-800' : 'bg-white'}`}>
        {/* Header with gradient accent */}
        <div className={`relative border-b ${darkMode ? 'bg-slate-700 border-slate-600' : 'bg-gradient-to-r from-gray-50 to-white border-gray-100'}`}>
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 via-cyan-500 to-blue-500"></div>
          <div className="flex justify-between items-center p-5">
            <h2 className={`text-xl font-bold ${darkMode ? 'text-white' : 'text-gray-800'}`}>{title}</h2>
            <button
              onClick={onClose}
              className={`p-2 rounded-lg transition-all duration-200 ${darkMode ? 'text-slate-400 hover:text-white hover:bg-slate-600' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'}`}
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
                  <option value="V1600GS-O32">V1600GS-O32 (Built-in Splitter)</option>
                  <option value="V1600GS-WB">V1600GS-WB</option>
                </optgroup>
                <optgroup label="GPON - 2 PON">
                  <option value="V1600GT">V1600GT</option>
                  <option value="V1600GT-2F">V1600GT-2F</option>
                </optgroup>
                <optgroup label="GPON - 4 PON">
                  <option value="V1600G0">V1600G0</option>
                  <option value="V1600G0-B">V1600G0-B</option>
                  <option value="V1600G0-R">V1600G0-R</option>
                  <option value="V1601G04">V1601G04</option>
                  <option value="V1601E04">V1601E04</option>
                </optgroup>
                <optgroup label="GPON - 8 PON">
                  <option value="V1600G1">V1600G1</option>
                  <option value="V1600G1-B">V1600G1-B</option>
                  <option value="V1600G1-R">V1600G1-R</option>
                  <option value="V1600G1-A">V1600G1-A</option>
                  <option value="V1600G1WEO">V1600G1WEO</option>
                  <option value="V1600G1WEO-B">V1600G1WEO-B (Outdoor IP65)</option>
                </optgroup>
                <optgroup label="GPON - 16 PON">
                  <option value="V1600G2">V1600G2</option>
                  <option value="V1600G2-B">V1600G2-B</option>
                  <option value="V1600G2-R">V1600G2-R</option>
                  <option value="V1600G2-A">V1600G2-A</option>
                </optgroup>
                <optgroup label="EPON - 1 PON">
                  <option value="V1600DS">V1600DS</option>
                </optgroup>
                <optgroup label="EPON - 2 PON">
                  <option value="V1600D2">V1600D2</option>
                  <option value="V1600D2-L">V1600D2-L</option>
                  <option value="V1601E02">V1601E02</option>
                  <option value="V1601E02-DP">V1601E02-DP</option>
                </optgroup>
                <optgroup label="EPON - 4 PON">
                  <option value="V1600D4">V1600D4</option>
                  <option value="V1600D4-L">V1600D4-L</option>
                  <option value="V1600D4-DP">V1600D4-DP</option>
                  <option value="V1600D-MINI">V1600D-MINI</option>
                  <option value="V1601E04-DP">V1601E04-DP</option>
                  <option value="V1601E04-BT">V1601E04-BT</option>
                </optgroup>
                <optgroup label="EPON - 8 PON">
                  <option value="V1600D8">V1600D8</option>
                  <option value="V1600D8-L">V1600D8-L</option>
                  <option value="V1600D8-R">V1600D8-R</option>
                </optgroup>
                <optgroup label="EPON - 16 PON">
                  <option value="V1600D16">V1600D16</option>
                  <option value="V1600D16-L">V1600D16-L</option>
                </optgroup>
                <optgroup label="10G XGS-PON - 2 PON">
                  <option value="V1600XG02">V1600XG02</option>
                  <option value="V1600XG02-W">V1600XG02-W</option>
                </optgroup>
                <optgroup label="10G XGS-PON - 4 PON">
                  <option value="V1600XG04">V1600XG04</option>
                </optgroup>
                <optgroup label="10G XGS-PON - 8 PON">
                  <option value="V3600G1">V3600G1</option>
                  <option value="V3600G1-C">V3600G1-C</option>
                  <option value="V3600D8">V3600D8</option>
                </optgroup>
                <optgroup label="10G XGS-PON - 16 PON">
                  <option value="V3600G2">V3600G2</option>
                </optgroup>
                <optgroup label="Chassis OLT">
                  <option value="V5600X2">V5600X2 (32 PON)</option>
                  <option value="V5600X4">V5600X4 (64 PON)</option>
                  <option value="V5600X7">V5600X7 (112 PON)</option>
                </optgroup>
                <optgroup label="Pizza Box OLT">
                  <option value="V1600P1">V1600P1 (1 PON)</option>
                  <option value="V1600P2">V1600P2 (2 PON)</option>
                  <option value="V1600P4">V1600P4 (4 PON)</option>
                  <option value="V1600P8">V1600P8 (8 PON)</option>
                </optgroup>
                <optgroup label="Custom">
                  <option value="Other">Other (Manual Entry)</option>
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

// Edit OLT Modal
function EditOLTModal({ isOpen, onClose, olt, onSubmit, regions }) {
  const [formData, setFormData] = useState({
    name: '',
    ip_address: '',
    username: '',
    password: '',
    snmp_community: 'public',
    model: '',
    pon_ports: 8,
  });
  const [loading, setLoading] = useState(false);
  const [ponPortsReadOnly, setPonPortsReadOnly] = useState(false);
  const [changePassword, setChangePassword] = useState(false);

  useEffect(() => {
    if (olt) {
      setFormData({
        name: olt.name || '',
        ip_address: olt.ip_address || '',
        username: olt.username || 'admin',
        password: '',
        snmp_community: olt.snmp_community || 'public',
        model: olt.model || '',
        pon_ports: olt.pon_ports || 8,
      });
      if (olt.model && VSOL_OLT_MODELS[olt.model]) {
        setPonPortsReadOnly(true);
      } else {
        setPonPortsReadOnly(false);
      }
      setChangePassword(false);
    }
  }, [olt]);

  const handleModelChange = (model) => {
    if (model && model !== 'Other' && VSOL_OLT_MODELS[model]) {
      setFormData({ ...formData, model, pon_ports: VSOL_OLT_MODELS[model] });
      setPonPortsReadOnly(true);
    } else {
      setFormData({ ...formData, model, pon_ports: model === 'Other' ? formData.pon_ports : 8 });
      setPonPortsReadOnly(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = { ...formData };
      // Only include password if user wants to change it
      if (!changePassword || !data.password) {
        delete data.password;
      }
      await onSubmit(olt.id, data);
      onClose();
    } catch (error) {
      alert('Failed to update OLT: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  if (!olt) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Edit OLT: ${olt.name}`} size="lg">
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                OLT Password
                <label className="inline-flex items-center ml-3 cursor-pointer">
                  <input
                    type="checkbox"
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    checked={changePassword}
                    onChange={(e) => setChangePassword(e.target.checked)}
                  />
                  <span className="ml-1 text-xs text-gray-500">Change</span>
                </label>
              </label>
              <input
                type="password"
                className="w-full rounded-lg border-gray-300 shadow-sm border p-3 focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder={changePassword ? "New password" : "••••••••"}
                disabled={!changePassword}
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
                  <option value="V1600GS-O32">V1600GS-O32 (Built-in Splitter)</option>
                  <option value="V1600GS-WB">V1600GS-WB</option>
                </optgroup>
                <optgroup label="GPON - 2 PON">
                  <option value="V1600GT">V1600GT</option>
                  <option value="V1600GT-2F">V1600GT-2F</option>
                </optgroup>
                <optgroup label="GPON - 4 PON">
                  <option value="V1600G0">V1600G0</option>
                  <option value="V1600G0-B">V1600G0-B</option>
                  <option value="V1600G0-R">V1600G0-R</option>
                  <option value="V1601G04">V1601G04</option>
                  <option value="V1601E04">V1601E04</option>
                </optgroup>
                <optgroup label="GPON - 8 PON">
                  <option value="V1600G1">V1600G1</option>
                  <option value="V1600G1-B">V1600G1-B</option>
                  <option value="V1600G1-R">V1600G1-R</option>
                  <option value="V1600G1-A">V1600G1-A</option>
                  <option value="V1600G1WEO">V1600G1WEO</option>
                  <option value="V1600G1WEO-B">V1600G1WEO-B (Outdoor IP65)</option>
                </optgroup>
                <optgroup label="GPON - 16 PON">
                  <option value="V1600G2">V1600G2</option>
                  <option value="V1600G2-B">V1600G2-B</option>
                  <option value="V1600G2-R">V1600G2-R</option>
                  <option value="V1600G2-A">V1600G2-A</option>
                </optgroup>
                <optgroup label="EPON - 1 PON">
                  <option value="V1600DS">V1600DS</option>
                </optgroup>
                <optgroup label="EPON - 2 PON">
                  <option value="V1600D2">V1600D2</option>
                  <option value="V1600D2-L">V1600D2-L</option>
                  <option value="V1601E02">V1601E02</option>
                  <option value="V1601E02-DP">V1601E02-DP</option>
                </optgroup>
                <optgroup label="EPON - 4 PON">
                  <option value="V1600D4">V1600D4</option>
                  <option value="V1600D4-L">V1600D4-L</option>
                  <option value="V1600D4-DP">V1600D4-DP</option>
                  <option value="V1600D-MINI">V1600D-MINI</option>
                  <option value="V1601E04-DP">V1601E04-DP</option>
                  <option value="V1601E04-BT">V1601E04-BT</option>
                </optgroup>
                <optgroup label="EPON - 8 PON">
                  <option value="V1600D8">V1600D8</option>
                  <option value="V1600D8-L">V1600D8-L</option>
                  <option value="V1600D8-R">V1600D8-R</option>
                </optgroup>
                <optgroup label="EPON - 16 PON">
                  <option value="V1600D16">V1600D16</option>
                  <option value="V1600D16-L">V1600D16-L</option>
                </optgroup>
                <optgroup label="10G XGS-PON - 2 PON">
                  <option value="V1600XG02">V1600XG02</option>
                  <option value="V1600XG02-W">V1600XG02-W</option>
                </optgroup>
                <optgroup label="10G XGS-PON - 4 PON">
                  <option value="V1600XG04">V1600XG04</option>
                </optgroup>
                <optgroup label="10G XGS-PON - 8 PON">
                  <option value="V3600G1">V3600G1</option>
                  <option value="V3600G1-C">V3600G1-C</option>
                  <option value="V3600D8">V3600D8</option>
                </optgroup>
                <optgroup label="10G XGS-PON - 16 PON">
                  <option value="V3600G2">V3600G2</option>
                </optgroup>
                <optgroup label="Chassis OLT">
                  <option value="V5600X2">V5600X2 (32 PON)</option>
                  <option value="V5600X4">V5600X4 (64 PON)</option>
                  <option value="V5600X7">V5600X7 (112 PON)</option>
                </optgroup>
                <optgroup label="Pizza Box OLT">
                  <option value="V1600P1">V1600P1 (1 PON)</option>
                  <option value="V1600P2">V1600P2 (2 PON)</option>
                  <option value="V1600P4">V1600P4 (4 PON)</option>
                  <option value="V1600P8">V1600P8 (8 PON)</option>
                </optgroup>
                <optgroup label="Custom">
                  <option value="Other">Other (Manual Entry)</option>
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
function SettingsModal({ isOpen, onClose, settings, onSubmit, onChangePassword, licenseInfo, defaultTab = 'general' }) {
  const darkMode = useContext(DarkModeContext);
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
  const [activeTab, setActiveTab] = useState(defaultTab);
  const [newRecipient, setNewRecipient] = useState({ name: '', phone: '' });
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [updateInfo, setUpdateInfo] = useState(null);
  const [updateStatus, setUpdateStatus] = useState(null);
  const [updating, setUpdating] = useState(false);

  // Dev Server / Publisher states
  const [isDevServer, setIsDevServer] = useState(false);
  const [publishVersion, setPublishVersion] = useState('');
  const [publishChangelog, setPublishChangelog] = useState('');
  const [publishing, setPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState(null);

  // Remote Access Tunnel states
  const [tunnelStatus, setTunnelStatus] = useState(null);
  const [tunnelLoading, setTunnelLoading] = useState(false);
  const [tunnelError, setTunnelError] = useState(null);

  // Update activeTab when defaultTab changes (when modal opens with specific tab)
  useEffect(() => {
    if (isOpen) {
      setActiveTab(defaultTab);
    }
  }, [isOpen, defaultTab]);

  // Check if this is dev server
  useEffect(() => {
    const checkDevServer = async () => {
      try {
        const response = await api.getDevStatus();
        setIsDevServer(response.data.is_dev_server);
        if (response.data.current_version) {
          // Suggest next version
          const parts = response.data.current_version.split('.');
          parts[2] = parseInt(parts[2] || 0) + 1;
          setPublishVersion(parts.join('.'));
        }
      } catch (error) {
        setIsDevServer(false);
      }
    };
    checkDevServer();
  }, []);

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

  // Fetch tunnel status when tunnel tab is selected
  const fetchTunnelStatus = async () => {
    try {
      setTunnelLoading(true);
      setTunnelError(null);
      const response = await api.getTunnelStatus();
      setTunnelStatus(response.data);
    } catch (error) {
      if (error.response?.status === 501) {
        setTunnelStatus({ available: false, message: 'Remote access feature not available on this installation' });
      } else {
        setTunnelError(error.response?.data?.detail || 'Failed to get tunnel status');
      }
    } finally {
      setTunnelLoading(false);
    }
  };

  const handleEnableTunnel = async () => {
    try {
      setTunnelLoading(true);
      setTunnelError(null);
      const response = await api.enableTunnel();
      if (response.data.success) {
        setTunnelStatus({ ...tunnelStatus, running: true, url: response.data.url, subdomain: response.data.subdomain });
        await fetchTunnelStatus();
      } else {
        setTunnelError(response.data.error || 'Failed to enable tunnel');
      }
    } catch (error) {
      setTunnelError(error.response?.data?.detail || error.response?.data?.error || 'Failed to enable tunnel');
    } finally {
      setTunnelLoading(false);
    }
  };

  const handleDisableTunnel = async () => {
    try {
      setTunnelLoading(true);
      setTunnelError(null);
      const response = await api.disableTunnel();
      if (response.data.success) {
        await fetchTunnelStatus();
      } else {
        setTunnelError(response.data.error || 'Failed to disable tunnel');
      }
    } catch (error) {
      setTunnelError(error.response?.data?.detail || 'Failed to disable tunnel');
    } finally {
      setTunnelLoading(false);
    }
  };

  // Fetch tunnel status when tab changes to tunnel
  useEffect(() => {
    if (activeTab === 'tunnel') {
      fetchTunnelStatus();
    }
  }, [activeTab]);

  const handleCheckForUpdate = async () => {
    setCheckingUpdate(true);
    try {
      const response = await api.checkForUpdates();
      setUpdateInfo(response.data);
      if (!response.data.update_available) {
        alert('You are running the latest version (v' + response.data.current_version + ')');
      }
    } catch (error) {
      alert('Failed to check for updates: ' + (error.response?.data?.detail || error.message));
    } finally {
      setCheckingUpdate(false);
    }
  };

  const handleAutoUpdate = async () => {
    if (!window.confirm('This will download and install the update automatically. The system will restart after installation. Continue?')) {
      return;
    }

    setUpdating(true);
    setUpdateStatus({ stage: 'preparing', progress: 0 });

    try {
      // Step 1: Download update
      setUpdateStatus({ stage: 'downloading', progress: 10 });
      const downloadResponse = await api.downloadUpdate();

      if (!downloadResponse.data.success) {
        throw new Error(downloadResponse.data.message || 'Download failed');
      }

      setUpdateStatus({ stage: 'downloaded', progress: 50, version: downloadResponse.data.version });

      // Step 2: Install update
      setUpdateStatus({ stage: 'installing', progress: 60 });
      const installResponse = await api.installUpdate();

      if (!installResponse.data.success) {
        throw new Error(installResponse.data.message || 'Installation failed');
      }

      setUpdateStatus({ stage: 'restarting', progress: 95 });

      // Wait a moment then show completion
      setTimeout(() => {
        setUpdateStatus({ stage: 'completed', progress: 100, message: 'Update installed! Reloading page...' });

        // Reload page after a few seconds
        setTimeout(() => {
          window.location.reload();
        }, 3000);
      }, 2000);

    } catch (error) {
      console.error('Update failed:', error);
      setUpdateStatus({
        stage: 'error',
        progress: 0,
        error: error.response?.data?.detail || error.message || 'Update failed'
      });
      setUpdating(false);
    }
  };

  // Handle publishing update to customers (dev server only)
  const handlePublish = async () => {
    if (!publishVersion || !publishChangelog) {
      alert('Please enter version number and changelog');
      return;
    }

    if (!window.confirm(`Publish version ${publishVersion} to all customers?\n\nChangelog:\n${publishChangelog}`)) {
      return;
    }

    setPublishing(true);
    setPublishResult(null);

    try {
      const response = await api.publishUpdate(publishVersion, publishChangelog);
      setPublishResult({
        success: true,
        message: response.data.message,
        steps: response.data.steps
      });
      // Increment version for next publish
      const parts = publishVersion.split('.');
      parts[2] = parseInt(parts[2] || 0) + 1;
      setPublishVersion(parts.join('.'));
      setPublishChangelog('');
    } catch (error) {
      setPublishResult({
        success: false,
        message: error.response?.data?.detail || error.message || 'Publish failed'
      });
    } finally {
      setPublishing(false);
    }
  };

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
      <div className={`flex border-b mb-4 overflow-x-auto ${darkMode ? 'border-slate-600' : ''}`}>
        <button
          className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'general' ? 'text-blue-600 border-b-2 border-blue-600' : darkMode ? 'text-slate-400' : 'text-gray-500'}`}
          onClick={() => setActiveTab('general')}
        >
          General
        </button>
        <button
          className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'whatsapp' ? 'text-blue-600 border-b-2 border-blue-600' : darkMode ? 'text-slate-400' : 'text-gray-500'}`}
          onClick={() => setActiveTab('whatsapp')}
        >
          WhatsApp
        </button>
        <button
          className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'password' ? 'text-blue-600 border-b-2 border-blue-600' : darkMode ? 'text-slate-400' : 'text-gray-500'}`}
          onClick={() => setActiveTab('password')}
        >
          Password
        </button>
        <button
          className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'license' ? 'text-blue-600 border-b-2 border-blue-600' : darkMode ? 'text-slate-400' : 'text-gray-500'}`}
          onClick={() => setActiveTab('license')}
        >
          License
        </button>
        <button
          className={`px-4 py-2 font-medium whitespace-nowrap ${activeTab === 'tunnel' ? 'text-blue-600 border-b-2 border-blue-600' : darkMode ? 'text-slate-400' : 'text-gray-500'}`}
          onClick={() => setActiveTab('tunnel')}
        >
          Remote Access
        </button>
      </div>

      {activeTab === 'general' && (
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>System Name</label>
              <input
                type="text"
                className={`w-full rounded-lg shadow-sm border p-3 focus:ring-2 focus:ring-blue-500 ${darkMode ? 'bg-slate-700 border-slate-600 text-white' : 'border-gray-300'}`}
                value={formData.system_name}
                onChange={(e) => setFormData({ ...formData, system_name: e.target.value })}
                placeholder="OLT Manager"
              />
              <p className={`text-xs mt-1 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Name displayed in header and browser title</p>
            </div>
            <div>
              <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>Polling Interval (seconds)</label>
              <input
                type="number"
                min="60"
                max="3600"
                className={`w-full rounded-lg shadow-sm border p-3 focus:ring-2 focus:ring-blue-500 ${darkMode ? 'bg-slate-700 border-slate-600 text-white' : 'border-gray-300'}`}
                value={formData.polling_interval}
                onChange={(e) => setFormData({ ...formData, polling_interval: parseInt(e.target.value) })}
              />
              <p className={`text-xs mt-1 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>How often to poll OLTs for ONU status (60-3600 seconds)</p>
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
            <div className={`flex items-center justify-between p-4 rounded-xl border ${darkMode ? 'bg-green-900/30 border-green-800' : 'bg-gradient-to-r from-green-50 to-green-100 border-green-200'}`}>
              <div className="flex items-center">
                <div className="w-12 h-12 bg-green-500 rounded-full flex items-center justify-center mr-3">
                  <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                  </svg>
                </div>
                <div>
                  <h3 className={`font-semibold text-lg ${darkMode ? 'text-green-400' : 'text-green-800'}`}>WhatsApp Notifications</h3>
                  <p className={`text-sm ${darkMode ? 'text-green-300' : 'text-green-600'}`}>Get alerts when ONUs go offline or come back online</p>
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
                <span className={`ml-3 text-sm font-medium ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>{formData.whatsapp_enabled ? 'ON' : 'OFF'}</span>
              </label>
            </div>

            {/* API Configuration - Always visible */}
            <div className={`space-y-4 p-4 rounded-xl border ${darkMode ? (formData.whatsapp_enabled ? 'bg-slate-700 border-slate-600' : 'bg-slate-700/50 border-slate-600') : (formData.whatsapp_enabled ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-100')}`}>
              <h4 className={`font-medium flex items-center ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>
                <svg className={`w-5 h-5 mr-2 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                API Configuration
              </h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>API URL</label>
                  <input
                    type="url"
                    className={`w-full rounded-lg border shadow-sm p-3 focus:ring-2 focus:ring-green-500 focus:border-green-500 ${darkMode ? 'bg-slate-600 border-slate-500 text-white' : 'border-gray-300'} ${!formData.whatsapp_enabled ? (darkMode ? 'bg-slate-600/50 text-slate-400' : 'bg-gray-100 text-gray-500') : ''}`}
                    value={formData.whatsapp_api_url}
                    onChange={(e) => setFormData({ ...formData, whatsapp_api_url: e.target.value })}
                    placeholder="https://proxsms.com/api/send/whatsapp"
                  />
                </div>
                <div>
                  <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>Secret Key</label>
                  <input
                    type="password"
                    className={`w-full rounded-lg border shadow-sm p-3 focus:ring-2 focus:ring-green-500 focus:border-green-500 ${darkMode ? 'bg-slate-600 border-slate-500 text-white' : 'border-gray-300'} ${!formData.whatsapp_enabled ? (darkMode ? 'bg-slate-600/50 text-slate-400' : 'bg-gray-100 text-gray-500') : ''}`}
                    value={formData.whatsapp_secret}
                    onChange={(e) => setFormData({ ...formData, whatsapp_secret: e.target.value })}
                    placeholder="Your ProxSMS secret key"
                  />
                </div>
              </div>

              <div>
                <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>Device ID (Account)</label>
                <input
                  type="text"
                  className={`w-full rounded-lg border shadow-sm p-3 focus:ring-2 focus:ring-green-500 focus:border-green-500 ${darkMode ? 'bg-slate-600 border-slate-500 text-white' : 'border-gray-300'} ${!formData.whatsapp_enabled ? (darkMode ? 'bg-slate-600/50 text-slate-400' : 'bg-gray-100 text-gray-500') : ''}`}
                  value={formData.whatsapp_account}
                  onChange={(e) => setFormData({ ...formData, whatsapp_account: e.target.value })}
                  placeholder="Your WhatsApp device ID"
                />
              </div>
            </div>

            {/* Recipients Management */}
            <div className={`space-y-4 p-4 rounded-xl border ${darkMode ? (formData.whatsapp_enabled ? 'bg-slate-700 border-slate-600' : 'bg-slate-700/50 border-slate-600') : (formData.whatsapp_enabled ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-100')}`}>
              <h4 className={`font-medium flex items-center ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>
                <svg className={`w-5 h-5 mr-2 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                Recipients ({formData.whatsapp_recipients.length})
              </h4>

              {/* Add New Recipient */}
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  type="text"
                  placeholder="Name"
                  className={`flex-1 rounded-lg border shadow-sm p-2.5 text-sm focus:ring-2 focus:ring-green-500 ${darkMode ? 'bg-slate-600 border-slate-500 text-white placeholder-slate-400' : 'border-gray-300'} ${!formData.whatsapp_enabled ? (darkMode ? 'bg-slate-600/50 text-slate-400' : 'bg-gray-100 text-gray-500') : ''}`}
                  value={newRecipient.name}
                  onChange={(e) => setNewRecipient({ ...newRecipient, name: e.target.value })}
                />
                <input
                  type="tel"
                  placeholder="Phone (+961...)"
                  className={`flex-1 rounded-lg border shadow-sm p-2.5 text-sm focus:ring-2 focus:ring-green-500 ${darkMode ? 'bg-slate-600 border-slate-500 text-white placeholder-slate-400' : 'border-gray-300'} ${!formData.whatsapp_enabled ? (darkMode ? 'bg-slate-600/50 text-slate-400' : 'bg-gray-100 text-gray-500') : ''}`}
                  value={newRecipient.phone}
                  onChange={(e) => setNewRecipient({ ...newRecipient, phone: e.target.value })}
                />
                <button
                  type="button"
                  onClick={addRecipient}
                  disabled={!formData.whatsapp_enabled}
                  className="px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 text-sm font-medium"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                  </svg>
                  Add
                </button>
              </div>

              {/* Recipients List */}
              {formData.whatsapp_recipients.length > 0 ? (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {formData.whatsapp_recipients.map((recipient, index) => (
                    <div key={index} className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${darkMode ? 'bg-slate-600 border-slate-500 hover:bg-slate-500' : 'bg-gray-50 border-gray-100 hover:bg-gray-100'}`}>
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-green-100 text-green-600 rounded-full flex items-center justify-center font-semibold text-sm">
                          {recipient.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className={`font-medium text-sm ${darkMode ? 'text-white' : 'text-gray-800'}`}>{recipient.name}</p>
                          <p className={`text-xs ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>{recipient.phone}</p>
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
                <div className={`text-center py-6 ${darkMode ? 'text-slate-500' : 'text-gray-400'}`}>
                  <svg className="w-10 h-10 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <p className="text-sm">No recipients added yet</p>
                  <p className="text-xs">Add recipients to receive notifications</p>
                </div>
              )}
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
              <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>Current Password</label>
              <input
                type="password"
                required
                className={`w-full rounded-lg shadow-sm border p-3 focus:ring-2 focus:ring-blue-500 ${darkMode ? 'bg-slate-700 border-slate-600 text-white' : 'border-gray-300'}`}
                value={passwordData.current_password}
                onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
              />
            </div>
            <div>
              <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>New Password</label>
              <input
                type="password"
                required
                minLength="6"
                className={`w-full rounded-lg shadow-sm border p-3 focus:ring-2 focus:ring-blue-500 ${darkMode ? 'bg-slate-700 border-slate-600 text-white' : 'border-gray-300'}`}
                value={passwordData.new_password}
                onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
              />
            </div>
            <div>
              <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>Confirm New Password</label>
              <input
                type="password"
                required
                className={`w-full rounded-lg shadow-sm border p-3 focus:ring-2 focus:ring-blue-500 ${darkMode ? 'bg-slate-700 border-slate-600 text-white' : 'border-gray-300'}`}
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

      {activeTab === 'license' && (
        <div className="space-y-4">
          {/* License Status Card */}
          <div className={`p-4 rounded-xl border ${
            licenseInfo?.status === 'active' ? (darkMode ? 'bg-green-900/30 border-green-800' : 'bg-green-50 border-green-200') :
            licenseInfo?.status === 'suspended' ? (darkMode ? 'bg-yellow-900/30 border-yellow-800' : 'bg-yellow-50 border-yellow-200') :
            licenseInfo?.status === 'expired' ? (darkMode ? 'bg-red-900/30 border-red-800' : 'bg-red-50 border-red-200') :
            (darkMode ? 'bg-slate-700 border-slate-600' : 'bg-gray-50 border-gray-200')
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <div className={`w-12 h-12 rounded-full flex items-center justify-center mr-3 ${
                  licenseInfo?.status === 'active' ? 'bg-green-500' :
                  licenseInfo?.status === 'suspended' ? 'bg-yellow-500' :
                  licenseInfo?.status === 'expired' ? 'bg-red-500' :
                  'bg-gray-500'
                }`}>
                  {licenseInfo?.status === 'active' ? (
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : licenseInfo?.status === 'suspended' ? (
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  ) : (
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  )}
                </div>
                <div>
                  <h3 className={`font-semibold text-lg ${
                    licenseInfo?.status === 'active' ? (darkMode ? 'text-green-400' : 'text-green-800') :
                    licenseInfo?.status === 'suspended' ? (darkMode ? 'text-yellow-400' : 'text-yellow-800') :
                    licenseInfo?.status === 'expired' ? (darkMode ? 'text-red-400' : 'text-red-800') :
                    (darkMode ? 'text-slate-300' : 'text-gray-800')
                  }`}>
                    {licenseInfo?.status === 'active' ? 'License Active' :
                     licenseInfo?.status === 'suspended' ? 'License Suspended' :
                     licenseInfo?.status === 'expired' ? 'License Expired' :
                     'License Invalid'}
                  </h3>
                  <p className={`text-sm ${
                    licenseInfo?.status === 'active' ? (darkMode ? 'text-green-300' : 'text-green-600') :
                    licenseInfo?.status === 'suspended' ? (darkMode ? 'text-yellow-300' : 'text-yellow-600') :
                    licenseInfo?.status === 'expired' ? (darkMode ? 'text-red-300' : 'text-red-600') :
                    (darkMode ? 'text-slate-400' : 'text-gray-600')
                  }`}>
                    {licenseInfo?.customer_name || 'Unknown'}
                  </p>
                </div>
              </div>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                licenseInfo?.status === 'active' ? 'bg-green-200 text-green-800' :
                licenseInfo?.status === 'suspended' ? 'bg-yellow-200 text-yellow-800' :
                licenseInfo?.status === 'expired' ? 'bg-red-200 text-red-800' :
                'bg-gray-200 text-gray-800'
              }`}>
                {licenseInfo?.license_type?.toUpperCase() || licenseInfo?.package_type?.toUpperCase() || 'STANDARD'}
              </span>
            </div>
          </div>

          {/* License Details */}
          <div className={`border rounded-xl p-4 ${darkMode ? 'bg-slate-700 border-slate-600' : 'bg-white border-gray-200'}`}>
            <h4 className={`font-medium mb-4 flex items-center ${darkMode ? 'text-slate-200' : 'text-gray-700'}`}>
              <svg className={`w-5 h-5 mr-2 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              License Details
            </h4>
            <div className="space-y-3">
              <div className={`flex justify-between items-center py-2 border-b ${darkMode ? 'border-slate-600' : 'border-gray-100'}`}>
                <span className={darkMode ? 'text-slate-300' : 'text-gray-600'}>License Key</span>
                <span className={`font-mono text-sm px-2 py-1 rounded ${darkMode ? 'bg-slate-600 text-slate-200' : 'bg-gray-100'}`}>
                  {licenseInfo?.license_key || 'N/A'}
                </span>
              </div>
              <div className={`flex justify-between items-center py-2 border-b ${darkMode ? 'border-slate-600' : 'border-gray-100'}`}>
                <span className={darkMode ? 'text-slate-300' : 'text-gray-600'}>Status</span>
                <span className={`font-medium ${
                  licenseInfo?.status === 'active' ? 'text-green-600' :
                  licenseInfo?.status === 'suspended' ? 'text-yellow-600' :
                  'text-red-600'
                }`}>
                  {licenseInfo?.status?.charAt(0).toUpperCase() + licenseInfo?.status?.slice(1) || 'Unknown'}
                </span>
              </div>
              <div className={`flex justify-between items-center py-2 border-b ${darkMode ? 'border-slate-600' : 'border-gray-100'}`}>
                <span className={darkMode ? 'text-slate-300' : 'text-gray-600'}>Expires</span>
                <span className={`font-medium ${darkMode ? 'text-white' : ''}`}>
                  {licenseInfo?.expires_at ? new Date(licenseInfo.expires_at).toLocaleDateString() : 'Never'}
                </span>
              </div>
              <div className={`flex justify-between items-center py-2 border-b ${darkMode ? 'border-slate-600' : 'border-gray-100'}`}>
                <span className={darkMode ? 'text-slate-300' : 'text-gray-600'}>Days Remaining</span>
                <span className={`font-bold text-lg ${
                  licenseInfo?.days_remaining <= 7 ? 'text-red-600' :
                  licenseInfo?.days_remaining <= 30 ? 'text-yellow-600' :
                  'text-green-600'
                }`}>
                  {licenseInfo?.days_remaining !== undefined ?
                    (licenseInfo.days_remaining < 0 ? 'Expired' :
                     licenseInfo.days_remaining === 0 ? 'Expires Today' :
                     `${licenseInfo.days_remaining} days`) :
                    'Unlimited'}
                </span>
              </div>
            </div>
          </div>

          {/* License Limits */}
          <div className={`border rounded-xl p-4 ${darkMode ? 'bg-slate-700 border-slate-600' : 'bg-white border-gray-200'}`}>
            <h4 className={`font-medium mb-4 flex items-center ${darkMode ? 'text-slate-200' : 'text-gray-700'}`}>
              <svg className={`w-5 h-5 mr-2 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              License Limits
            </h4>
            <div className="grid grid-cols-3 gap-4">
              <div className={`text-center p-3 rounded-lg ${darkMode ? 'bg-blue-900/30' : 'bg-blue-50'}`}>
                <div className={`text-2xl font-bold ${darkMode ? 'text-blue-400' : 'text-blue-600'}`}>{licenseInfo?.max_olts || 0}</div>
                <div className={`text-sm ${darkMode ? 'text-blue-300' : 'text-blue-700'}`}>Max OLTs</div>
              </div>
              <div className={`text-center p-3 rounded-lg ${darkMode ? 'bg-purple-900/30' : 'bg-purple-50'}`}>
                <div className={`text-2xl font-bold ${darkMode ? 'text-purple-400' : 'text-purple-600'}`}>{licenseInfo?.max_onus || 0}</div>
                <div className={`text-sm ${darkMode ? 'text-purple-300' : 'text-purple-700'}`}>Max ONUs</div>
              </div>
              <div className={`text-center p-3 rounded-lg ${darkMode ? 'bg-teal-900/30' : 'bg-teal-50'}`}>
                <div className={`text-2xl font-bold ${darkMode ? 'text-teal-400' : 'text-teal-600'}`}>{licenseInfo?.max_users || 0}</div>
                <div className={`text-sm ${darkMode ? 'text-teal-300' : 'text-teal-700'}`}>Max Users</div>
              </div>
            </div>
          </div>

          {/* Features */}
          {licenseInfo?.features && licenseInfo.features.length > 0 && (
            <div className={`border rounded-xl p-4 ${darkMode ? 'bg-slate-700 border-slate-600' : 'bg-white border-gray-200'}`}>
              <h4 className={`font-medium mb-3 flex items-center ${darkMode ? 'text-slate-200' : 'text-gray-700'}`}>
                <svg className={`w-5 h-5 mr-2 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Included Features
              </h4>
              <div className="flex flex-wrap gap-2">
                {licenseInfo.features.map((feature, idx) => (
                  <span key={idx} className={`px-3 py-1 rounded-full text-sm font-medium ${darkMode ? 'bg-green-900/40 text-green-400' : 'bg-green-100 text-green-700'}`}>
                    {feature.charAt(0).toUpperCase() + feature.slice(1)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Hardware ID */}
          <div className={`border rounded-xl p-4 ${darkMode ? 'bg-slate-700/50 border-slate-600' : 'bg-gray-50 border-gray-200'}`}>
            <div className="flex justify-between items-center">
              <span className={`text-sm ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>Hardware ID</span>
              <span className={`font-mono text-xs ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>{licenseInfo?.hardware_id || 'N/A'}</span>
            </div>
          </div>

          {/* Check for Updates */}
          <div className={`border rounded-xl p-4 ${darkMode ? 'bg-slate-700 border-slate-600' : 'bg-white border-gray-200'}`}>
            <h4 className={`font-medium mb-4 flex items-center ${darkMode ? 'text-slate-200' : 'text-gray-700'}`}>
              <svg className={`w-5 h-5 mr-2 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Software Updates
            </h4>

            {/* Update Available Banner */}
            {updateInfo?.update_available && updateInfo.update && (
              <div className="mb-4 p-4 bg-gradient-to-r from-blue-500 to-blue-600 rounded-xl text-white">
                <div className="flex items-start justify-between">
                  <div className="flex items-center">
                    <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center mr-3">
                      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
                      </svg>
                    </div>
                    <div>
                      <h5 className="font-bold text-lg">Update Available!</h5>
                      <p className="text-blue-100 text-sm">
                        Version {updateInfo.update.latest_version} is available (You have v{updateInfo.current_version})
                      </p>
                    </div>
                  </div>
                </div>
                {updateInfo.update.changelog && (
                  <div className="mt-3 p-3 bg-white/10 rounded-lg">
                    <p className="text-sm font-medium mb-1">What's New:</p>
                    <p className="text-sm text-blue-100">{updateInfo.update.changelog}</p>
                  </div>
                )}

                {/* Update Progress */}
                {updating && updateStatus && (
                  <div className="mt-4 p-4 bg-white/10 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">
                        {updateStatus.stage === 'preparing' && 'Preparing update...'}
                        {updateStatus.stage === 'downloading' && 'Downloading update...'}
                        {updateStatus.stage === 'downloaded' && 'Download complete'}
                        {updateStatus.stage === 'installing' && 'Installing update...'}
                        {updateStatus.stage === 'restarting' && 'Restarting service...'}
                        {updateStatus.stage === 'completed' && 'Update completed!'}
                        {updateStatus.stage === 'error' && 'Update failed'}
                      </span>
                      <span className="text-sm">{updateStatus.progress}%</span>
                    </div>
                    <div className="w-full bg-white/20 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all duration-300 ${
                          updateStatus.stage === 'error' ? 'bg-red-400' :
                          updateStatus.stage === 'completed' ? 'bg-green-400' : 'bg-white'
                        }`}
                        style={{ width: `${updateStatus.progress}%` }}
                      ></div>
                    </div>
                    {updateStatus.error && (
                      <p className="mt-2 text-red-200 text-sm">{updateStatus.error}</p>
                    )}
                    {updateStatus.stage === 'completed' && (
                      <p className="mt-2 text-green-200 text-sm">Page will reload automatically...</p>
                    )}
                  </div>
                )}

                {/* Update Now Button - Always show when not updating */}
                <div className="mt-4">
                  <button
                    onClick={handleAutoUpdate}
                    disabled={updating}
                    className="inline-flex items-center px-5 py-2.5 bg-white text-blue-600 rounded-lg font-semibold hover:bg-blue-50 transition-colors shadow-lg disabled:opacity-50"
                  >
                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    {updating ? 'Updating...' : 'Update Now'}
                  </button>
                </div>
              </div>
            )}

            {/* No Update Available Message */}
            {updateInfo && !updateInfo.update_available && (
              <div className={`mb-4 p-4 rounded-xl border ${darkMode ? 'bg-green-900/30 border-green-800' : 'bg-green-50 border-green-200'}`}>
                <div className="flex items-center">
                  <svg className={`w-6 h-6 mr-3 ${darkMode ? 'text-green-400' : 'text-green-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <div>
                    <p className={`font-medium ${darkMode ? 'text-green-400' : 'text-green-800'}`}>You're up to date!</p>
                    <p className={`text-sm ${darkMode ? 'text-green-300' : 'text-green-600'}`}>Version {updateInfo.current_version} is the latest version.</p>
                  </div>
                </div>
              </div>
            )}

            <button
              onClick={handleCheckForUpdate}
              disabled={checkingUpdate}
              className="w-full flex items-center justify-center px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {checkingUpdate ? (
                <>
                  <svg className="w-5 h-5 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Checking for Updates...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Check for Updates
                </>
              )}
            </button>
          </div>

          {/* Dev Server: Publish Update Section */}
          {isDevServer && (
            <div className="mt-6 bg-gradient-to-r from-purple-600 to-indigo-600 rounded-xl p-5 text-white">
              <h4 className="font-bold text-lg mb-4 flex items-center">
                <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                Publish Update to Customers
              </h4>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-purple-200 mb-1">Version Number</label>
                  <input
                    type="text"
                    value={publishVersion}
                    onChange={(e) => setPublishVersion(e.target.value)}
                    placeholder="1.2.0"
                    className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-purple-300 focus:outline-none focus:ring-2 focus:ring-white/30"
                  />
                </div>

                <div>
                  <label className="block text-sm text-purple-200 mb-1">Changelog</label>
                  <textarea
                    value={publishChangelog}
                    onChange={(e) => setPublishChangelog(e.target.value)}
                    placeholder="- Fixed bugs&#10;- Added new features&#10;- Improved performance"
                    rows={4}
                    className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-purple-300 focus:outline-none focus:ring-2 focus:ring-white/30 resize-none"
                  />
                </div>

                {publishResult && (
                  <div className={`p-3 rounded-lg ${publishResult.success ? 'bg-green-500/20 border border-green-400' : 'bg-red-500/20 border border-red-400'}`}>
                    <p className="font-medium">{publishResult.success ? 'Success!' : 'Failed'}</p>
                    <p className="text-sm">{publishResult.message}</p>
                    {publishResult.steps && (
                      <ul className="mt-2 text-sm space-y-1">
                        {publishResult.steps.map((step, i) => (
                          <li key={i} className="flex items-center">
                            <svg className="w-4 h-4 mr-2 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            {step}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                <button
                  onClick={handlePublish}
                  disabled={publishing || !publishVersion || !publishChangelog}
                  className="w-full py-3 bg-white text-purple-600 font-bold rounded-lg hover:bg-purple-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                >
                  {publishing ? (
                    <>
                      <svg className="w-5 h-5 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Building & Publishing...
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                      Build & Publish Update
                    </>
                  )}
                </button>

                <p className="text-xs text-purple-200 text-center">
                  This will build frontend, create package, and upload to license server
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'tunnel' && (
        <div className="space-y-4">
          {/* Remote Access Header */}
          <div className="bg-gradient-to-r from-cyan-600 to-blue-600 rounded-xl p-5 text-white">
            <div className="flex items-center mb-3">
              <svg className="w-8 h-8 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <h4 className="font-bold text-lg">Remote Access</h4>
                <p className="text-cyan-100 text-sm">Access your OLT Manager from anywhere via secure tunnel</p>
              </div>
            </div>
          </div>

          {/* Loading State */}
          {tunnelLoading && (
            <div className="flex items-center justify-center py-8">
              <svg className="w-8 h-8 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className={`ml-3 ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>Loading tunnel status...</span>
            </div>
          )}

          {/* Error State */}
          {tunnelError && (
            <div className={`p-4 rounded-xl border ${darkMode ? 'bg-red-900/30 border-red-800' : 'bg-red-50 border-red-200'}`}>
              <div className="flex items-center">
                <svg className={`w-6 h-6 mr-3 ${darkMode ? 'text-red-400' : 'text-red-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <p className={`font-medium ${darkMode ? 'text-red-400' : 'text-red-800'}`}>Error</p>
                  <p className={`text-sm ${darkMode ? 'text-red-300' : 'text-red-600'}`}>{tunnelError}</p>
                </div>
              </div>
              <button
                onClick={fetchTunnelStatus}
                className={`mt-3 px-4 py-2 rounded-lg transition-colors ${darkMode ? 'bg-red-900/50 text-red-300 hover:bg-red-900/70' : 'bg-red-100 text-red-700 hover:bg-red-200'}`}
              >
                Retry
              </button>
            </div>
          )}

          {/* Not Available State */}
          {!tunnelLoading && tunnelStatus?.available === false && (
            <div className={`p-4 rounded-xl border ${darkMode ? 'bg-slate-700 border-slate-600' : 'bg-gray-50 border-gray-200'}`}>
              <div className="flex items-center">
                <svg className={`w-6 h-6 mr-3 ${darkMode ? 'text-slate-400' : 'text-gray-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                </svg>
                <p className={darkMode ? 'text-slate-300' : 'text-gray-600'}>{tunnelStatus.message || 'Remote access feature is not available'}</p>
              </div>
            </div>
          )}

          {/* Tunnel Status */}
          {!tunnelLoading && !tunnelError && tunnelStatus && tunnelStatus.available !== false && (
            <>
              {/* Status Card */}
              <div className={`p-4 rounded-xl border ${tunnelStatus.running ? (darkMode ? 'bg-green-900/30 border-green-800' : 'bg-green-50 border-green-200') : (darkMode ? 'bg-slate-700 border-slate-600' : 'bg-gray-50 border-gray-200')}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <div className={`w-4 h-4 rounded-full mr-3 ${tunnelStatus.running ? 'bg-green-500 animate-pulse' : (darkMode ? 'bg-slate-500' : 'bg-gray-400')}`}></div>
                    <div>
                      <p className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>
                        {tunnelStatus.running ? 'Tunnel Active' : 'Tunnel Inactive'}
                      </p>
                      <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                        {tunnelStatus.running ? 'Remote access is enabled' : 'Click enable to start remote access'}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={tunnelStatus.running ? handleDisableTunnel : handleEnableTunnel}
                    disabled={tunnelLoading}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 ${
                      tunnelStatus.running
                        ? 'bg-red-100 text-red-700 hover:bg-red-200'
                        : 'bg-green-600 text-white hover:bg-green-700'
                    }`}
                  >
                    {tunnelLoading ? 'Please wait...' : (tunnelStatus.running ? 'Disable' : 'Enable')}
                  </button>
                </div>
              </div>

              {/* Active Tunnel Info */}
              {tunnelStatus.running && tunnelStatus.url && (
                <div className={`p-4 rounded-xl border ${darkMode ? 'bg-blue-900/30 border-blue-800' : 'bg-blue-50 border-blue-200'}`}>
                  <h5 className={`font-semibold mb-3 flex items-center ${darkMode ? 'text-blue-400' : 'text-blue-800'}`}>
                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                    Your Remote Access URL
                  </h5>
                  <div className={`p-3 rounded-lg border ${darkMode ? 'bg-slate-700 border-blue-700' : 'bg-white border-blue-100'}`}>
                    <div className="flex items-center justify-between">
                      <a
                        href={tunnelStatus.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`font-mono text-lg break-all ${darkMode ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-800'}`}
                      >
                        {tunnelStatus.url}
                      </a>
                      <button
                        onClick={() => {
                          const textToCopy = tunnelStatus.url;
                          // Use textarea method - works on both HTTP and HTTPS
                          const textArea = document.createElement('textarea');
                          textArea.value = textToCopy;
                          textArea.style.position = 'fixed';
                          textArea.style.top = '0';
                          textArea.style.left = '0';
                          textArea.style.width = '2em';
                          textArea.style.height = '2em';
                          textArea.style.padding = '0';
                          textArea.style.border = 'none';
                          textArea.style.outline = 'none';
                          textArea.style.boxShadow = 'none';
                          textArea.style.background = 'transparent';
                          document.body.appendChild(textArea);
                          textArea.focus();
                          textArea.select();
                          try {
                            const successful = document.execCommand('copy');
                            if (successful) {
                              alert('URL copied to clipboard!');
                            } else {
                              prompt('Copy this URL:', textToCopy);
                            }
                          } catch (err) {
                            prompt('Copy this URL:', textToCopy);
                          }
                          document.body.removeChild(textArea);
                        }}
                        className={`ml-3 p-2 rounded-lg transition-colors flex-shrink-0 ${darkMode ? 'bg-blue-900/50 text-blue-400 hover:bg-blue-900/70' : 'bg-blue-100 text-blue-600 hover:bg-blue-200'}`}
                        title="Copy URL"
                      >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  <p className={`text-sm mt-2 ${darkMode ? 'text-blue-300' : 'text-blue-600'}`}>
                    Share this URL to access your OLT Manager from anywhere in the world.
                  </p>
                </div>
              )}

              {/* Info Box */}
              <div className={`p-4 rounded-xl border ${darkMode ? 'bg-cyan-900/30 border-cyan-800' : 'bg-cyan-50 border-cyan-200'}`}>
                <div className="flex items-start">
                  <svg className={`w-6 h-6 mt-0.5 mr-3 flex-shrink-0 ${darkMode ? 'text-cyan-400' : 'text-cyan-600'}`} fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <p className={`font-medium ${darkMode ? 'text-cyan-400' : 'text-cyan-800'}`}>How Remote Access Works</p>
                    <ul className={`text-sm mt-2 space-y-1 list-disc ml-4 ${darkMode ? 'text-cyan-300' : 'text-cyan-700'}`}>
                      <li>Creates a secure encrypted reverse SSH tunnel</li>
                      <li>No need to open ports or configure firewall</li>
                      <li>Works from any network, even behind NAT</li>
                      <li>Managed by your service provider for remote support</li>
                    </ul>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
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
      } else if (entityType === 'port') {
        // entityId format: "oltId:portType:portNumber"
        const [oltId, portType, portNumber] = entityId.split(':');
        url = `/api/olts/${oltId}/ports/${portType}/${portNumber}/traffic?range=${timeRange}`;
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

    // rx = Download (green), tx = Upload (cyan)
    // API returns rx_kbps as customer download traffic (bigger value)
    const downloadValues = rxValues;
    const uploadValues = txValues;

    // Draw Download - Green (the BIG number - rx)
    drawSmoothLine(downloadValues, '#22c55e', ['rgba(34, 197, 94, 0.4)', 'rgba(34, 197, 94, 0.02)']);

    // Draw Upload - Cyan/Blue (the small number - tx)
    drawSmoothLine(uploadValues, '#06b6d4', ['rgba(6, 182, 212, 0.35)', 'rgba(6, 182, 212, 0.02)']);

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

  // Calculate stats - ALWAYS use rx as Download (the bigger value from API)
  // API returns rx_kbps as the larger value for uplink ports (customer download)
  const stats = data && data.data && data.data.length > 0 ? (() => {
    // rx_kbps = Download (from internet to customers - bigger)
    // tx_kbps = Upload (from customers to internet - smaller)
    const rxMax = Math.max(...data.data.map(d => d.rx_kbps));
    const txMax = Math.max(...data.data.map(d => d.tx_kbps));
    const rxSum = data.data.reduce((sum, d) => sum + d.rx_kbps, 0);
    const txSum = data.data.reduce((sum, d) => sum + d.tx_kbps, 0);
    return {
      maxDownload: rxMax,
      maxUpload: txMax,
      avgDownload: rxSum / data.data.length,
      avgUpload: txSum / data.data.length,
      totalDownload: rxSum * 60 / 8 / 1024,
      totalUpload: txSum * 60 / 8 / 1024
    };
  })() : null;

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
                    <span className="text-green-400 font-bold">{formatBandwidth(tooltip.data.rx_kbps)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-cyan-500"></span>
                    <span className="text-slate-300">Upload:</span>
                    <span className="text-cyan-400 font-bold">{formatBandwidth(tooltip.data.tx_kbps)}</span>
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

// Port Icon Component for OLT visualization
function PortIcon({ type, number, status, onuCount, onClick, onEdit, isUplink, label }) {
  const isUp = status === 'up';
  const baseColor = isUp ? (isUplink ? 'bg-blue-500' : 'bg-green-500') : 'bg-gray-400';
  const hoverColor = isUp ? (isUplink ? 'hover:bg-blue-600' : 'hover:bg-green-600') : 'hover:bg-gray-500';
  const displayLabel = label || `${type.toUpperCase()}${number}`;
  const hasCustomLabel = label && label !== `${type.toUpperCase()}${number}` && label !== `GE${number}` && label !== `SFP${number}` && label !== `10G${number}`;

  const handleRightClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (isUplink && onEdit) {
      onEdit();
    }
  };

  return (
    <div
      className={`relative group cursor-pointer`}
      onClick={(e) => { e.stopPropagation(); onClick && onClick(); }}
      onContextMenu={handleRightClick}
      title={`${displayLabel} - ${isUp ? 'Online' : 'Offline'}${!isUplink && onuCount ? ` (${onuCount} ONUs)` : ''}${isUplink ? ' (Right-click to edit name)' : ''}`}
    >
      <div className={`w-8 h-8 ${baseColor} ${hoverColor} rounded flex items-center justify-center transition-all duration-150 shadow-sm ${hasCustomLabel ? 'ring-2 ring-yellow-400' : ''}`}>
        {isUplink ? (
          <span className="text-white text-[10px] font-bold">{number}</span>
        ) : (
          <span className="text-white text-xs font-bold">{number}</span>
        )}
      </div>
      {!isUplink && onuCount > 0 && (
        <span className="absolute -top-1 -right-1 bg-blue-600 text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
          {onuCount > 99 ? '99+' : onuCount}
        </span>
      )}
      {/* Connected indicator for uplink with custom label */}
      {isUplink && hasCustomLabel && (
        <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 bg-yellow-400 text-gray-900 text-[8px] font-bold px-1 rounded">
          {label.length > 6 ? label.substring(0, 6) : label}
        </span>
      )}
      {/* Edit icon on hover for uplink ports */}
      {isUplink && (
        <button
          onClick={(e) => { e.stopPropagation(); onEdit && onEdit(); }}
          className="absolute -top-1 -right-1 w-4 h-4 bg-gray-700 hover:bg-blue-600 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
          title="Edit port name"
        >
          <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
          </svg>
        </button>
      )}
      {/* Tooltip */}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10 pointer-events-none">
        GE{number}
        {hasCustomLabel && <span className="text-yellow-400"> ({label})</span>}
        {!isUplink && onuCount !== undefined && <span> ({onuCount} ONUs)</span>}
        <br />
        <span className={isUp ? 'text-green-400' : 'text-red-400'}>{isUp ? 'Online' : 'Offline'}</span>
      </div>
    </div>
  );
}

// OLT Card Component - Enterprise Pro Design with Port Visualization
function OLTCard({ olt, onSelect, onPoll, onDelete, onEdit, isSelected, isAdmin, onGraph, onPortGraph }) {
  const darkMode = useContext(DarkModeContext);
  const [polling, setPolling] = useState(false);
  const [ports, setPorts] = useState(null);
  const [loadingPorts, setLoadingPorts] = useState(false);
  const [showPorts, setShowPorts] = useState(true);
  const [editingPort, setEditingPort] = useState(null);
  const [portDescription, setPortDescription] = useState('');
  const [savingPort, setSavingPort] = useState(false);

  // Live health fluctuation state - CPU and RAM animate, TEMP uses real values only
  const [liveHealth, setLiveHealth] = useState({
    cpu: olt.cpu_usage,
    memory: olt.memory_usage
  });

  // Update CPU and RAM with slight fluctuations every second (TEMP excluded - real values only)
  useEffect(() => {
    if (!olt.is_online || olt.cpu_usage === null) return;

    const fluctuate = (base, range = 2) => {
      if (base === null || base === undefined) return null;
      const delta = Math.floor(Math.random() * (range * 2 + 1)) - range;
      return Math.max(0, Math.min(100, base + delta));
    };

    const interval = setInterval(() => {
      setLiveHealth({
        cpu: fluctuate(olt.cpu_usage, 3),
        memory: fluctuate(olt.memory_usage, 2)
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [olt.is_online, olt.cpu_usage, olt.memory_usage]);

  // Update base values when olt prop changes
  useEffect(() => {
    setLiveHealth({
      cpu: olt.cpu_usage,
      memory: olt.memory_usage
    });
  }, [olt.cpu_usage, olt.memory_usage]);

  // Get PON port count from model
  const ponPortCount = olt.model ? (VSOL_OLT_MODELS[olt.model] || olt.pon_ports || 8) : (olt.pon_ports || 8);

  // Fetch ports when card expands
  useEffect(() => {
    if (showPorts && !ports && !loadingPorts) {
      setLoadingPorts(true);
      api.getOltPorts(olt.id)
        .then(response => {
          setPorts(response.data);
        })
        .catch(err => {
          console.error('Failed to load ports:', err);
        })
        .finally(() => {
          setLoadingPorts(false);
        });
    }
  }, [showPorts, olt.id, ports, loadingPorts]);

  const handlePoll = async (e) => {
    e.stopPropagation();
    setPolling(true);
    try {
      await onPoll(olt.id);
      // Refresh ports after poll
      setPorts(null);
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

  const togglePorts = (e) => {
    e.stopPropagation();
    setShowPorts(!showPorts);
  };

  const handleEditPort = (portNumber, currentLabel) => {
    setEditingPort(portNumber);
    // Extract just the description part if label is like "GE9" or custom
    const desc = currentLabel && !currentLabel.startsWith('GE') ? currentLabel : '';
    setPortDescription(desc);
  };

  const handleSavePortDescription = async () => {
    if (!editingPort) return;
    setSavingPort(true);
    try {
      await api.put(`/api/olts/${olt.id}/ports/${editingPort}/description?description=${encodeURIComponent(portDescription)}`);
      // Refresh ports to show new description
      setPorts(null);
      setEditingPort(null);
      setPortDescription('');
    } catch (err) {
      console.error('Failed to save port description:', err);
      alert('Failed to save port description');
    } finally {
      setSavingPort(false);
    }
  };

  const handlePortClick = (portType, portNumber) => {
    if (onPortGraph) {
      onPortGraph(olt.id, olt.name, portType, portNumber);
    }
  };

  const onlinePercent = olt.onu_count > 0 ? Math.round((olt.online_onu_count / olt.onu_count) * 100) : 0;

  // Generate port data - use API data if available, otherwise generate defaults
  const ponPorts = ports?.pon_ports || Array.from({ length: ponPortCount }, (_, i) => ({
    port_number: i + 1,
    status: 'unknown',
    onu_count: 0
  }));

  // Combine all uplink ports: GE RJ45, SFP, and 10G SFP+
  const gePorts = (ports?.ge_ports || []).map(p => ({
    port_type: 'ge',
    port_number: p.port_number,
    status: p.status || 'unknown',
    label: p.label || `GE${p.port_number}`
  }));

  const sfpPorts = (ports?.sfp_ports || []).map(p => ({
    port_type: 'sfp',
    port_number: p.port_number,
    status: p.status || 'unknown',
    label: p.label || `SFP${p.port_number}`
  }));

  const xgePorts = (ports?.xge_ports || []).map(p => ({
    port_type: 'xge',
    port_number: p.port_number,
    status: p.status || 'unknown',
    label: p.label || `10G${p.port_number}`
  }));

  // Default fallback if no port data
  const uplinkPorts = [...gePorts, ...sfpPorts, ...xgePorts].length > 0
    ? [...gePorts, ...sfpPorts, ...xgePorts]
    : [
        { port_type: 'ge', port_number: 1, status: 'unknown', label: 'GE1' },
        { port_type: 'ge', port_number: 2, status: 'unknown', label: 'GE2' }
      ];

  return (
    <div
      onClick={() => onSelect(olt.id)}
      className={`rounded-xl border cursor-pointer transition-all duration-200 hover:shadow-sm overflow-hidden ${
        darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-[#e8eaed]'
      } ${isSelected ? 'ring-2 ring-[#2563eb] border-blue-500' : ''}`}
    >
      {/* Header */}
      <div className={`p-4 border-b ${darkMode ? 'border-slate-700' : 'border-[#e8eaed]'}`}>
        <div className="flex justify-between items-start">
          <div className="flex items-start gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              olt.is_online
                ? (darkMode ? 'bg-blue-900/50' : 'bg-blue-50')
                : (darkMode ? 'bg-slate-700' : 'bg-gray-100')
            }`}>
              <svg className={`w-5 h-5 ${olt.is_online ? 'text-blue-500' : (darkMode ? 'text-slate-500' : 'text-[#9ca3af]')}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
              </svg>
            </div>
            <div>
              <h3 className={`font-semibold ${darkMode ? 'text-white' : 'text-[#111827]'}`}>{olt.name}</h3>
              <p className={`text-sm font-mono ${darkMode ? 'text-slate-400' : 'text-[#9ca3af]'}`}>{olt.ip_address}</p>
            </div>
          </div>
          <StatusBadge online={olt.is_online} />
        </div>
      </div>

      {/* Body */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          {olt.model && <p className={`text-xs ${darkMode ? 'text-slate-400' : 'text-[#9ca3af]'}`}>{olt.model}</p>}
          <span className={`text-xs ${darkMode ? 'text-slate-400' : 'text-[#9ca3af]'}`}>{ponPortCount} PON Ports</span>
        </div>

        {/* Stats with progress bar */}
        <div className="mb-3">
          <div className="flex justify-between text-sm mb-1.5">
            <span className={darkMode ? 'text-slate-400' : 'text-[#4b5563]'}>ONUs Online</span>
            <span className={`font-medium ${darkMode ? 'text-white' : 'text-[#111827]'}`}>{olt.online_onu_count} / {olt.onu_count}</span>
          </div>
          <div className={`h-2 rounded-full overflow-hidden ${darkMode ? 'bg-slate-700' : 'bg-[#f4f5f7]'}`}>
            <div
              className={`h-full rounded-full transition-all duration-500 ${onlinePercent > 80 ? 'bg-[#059669]' : onlinePercent > 50 ? 'bg-amber-500' : 'bg-[#dc2626]'}`}
              style={{ width: `${onlinePercent}%` }}
            ></div>
          </div>
        </div>

        {/* OLT Health Metrics - Speedometer Dashboard Style */}
        {olt.is_online && (olt.cpu_usage !== null || olt.temperature !== null) && (
          <div className="mb-3 p-3 bg-gradient-to-br from-[#0f172a] to-[#1e293b] rounded-xl border border-[#334155]">
            {/* Uptime and Fan Speed display - FIRST */}
            <div className="mb-2 pb-2 border-b border-[#334155] flex items-center justify-center gap-4">
              {olt.uptime_seconds !== null && (
                <div className="flex items-center gap-1.5">
                  <svg className="w-3.5 h-3.5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-xs text-gray-400">Uptime: <span className="text-green-400 font-medium">{formatUptime(olt.uptime_seconds)}</span></span>
                </div>
              )}
              {/* Fan Speed - Based on real temperature (threshold 40°C) */}
              {olt.temperature !== null && (
                <div className="flex items-center gap-1.5">
                  <svg className={`w-3.5 h-3.5 animate-spin ${olt.temperature >= 40 ? 'text-orange-400' : 'text-blue-400'}`} style={{animationDuration: olt.temperature >= 40 ? '0.5s' : '2s'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <span className="text-xs text-gray-400">Fan: <span className={`font-medium ${olt.temperature >= 40 ? 'text-orange-400' : 'text-blue-400'}`}>{olt.temperature >= 40 ? 'High' : 'Normal'}</span></span>
                </div>
              )}
            </div>
            {/* Gauges Row - AFTER uptime */}
            <div className="flex justify-around items-start">
              <SpeedometerGauge
                value={liveHealth.cpu}
                max={100}
                label="CPU"
                unit="%"
              />
              <SpeedometerGauge
                value={liveHealth.memory}
                max={100}
                label="RAM"
                unit="%"
              />
              <SpeedometerGauge
                value={olt.temperature}
                max={80}
                label="TEMP"
                unit="°C"
                colorStops={[
                  { offset: 0, color: '#10b981' },
                  { offset: 60, color: '#f59e0b' },
                  { offset: 100, color: '#ef4444' }
                ]}
              />
            </div>
          </div>
        )}

        {/* Port Visualization Toggle */}
        <button
          onClick={togglePorts}
          className={`w-full py-2 px-3 mb-3 text-sm rounded-lg transition-all flex items-center justify-between ${
            darkMode ? 'text-slate-300 bg-slate-700 hover:bg-slate-600' : 'text-[#4b5563] bg-[#f4f5f7] hover:bg-[#e8eaed]'
          }`}
        >
          <span className="flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
            </svg>
            Port Status
          </span>
          <svg className={`w-4 h-4 transition-transform ${showPorts ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {/* Port Visualization Panel */}
        {showPorts && (
          <div className="bg-[#1a1a2e] rounded-lg p-4 mb-3" onClick={(e) => e.stopPropagation()}>
            {loadingPorts ? (
              <div className="flex items-center justify-center py-4">
                <svg className="animate-spin w-6 h-6 text-blue-500" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
              </div>
            ) : (
              <>
                {/* PON Ports */}
                <div className="mb-4">
                  <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">PON Ports</p>
                  <div className="flex flex-wrap gap-2">
                    {ponPorts.map((port) => (
                      <PortIcon
                        key={`pon-${port.port_number}`}
                        type="pon"
                        number={port.port_number}
                        status={port.status}
                        onuCount={port.onu_count}
                        onClick={() => handlePortClick('pon', port.port_number)}
                      />
                    ))}
                  </div>
                </div>

                {/* Uplink Ports - Grouped by Type */}
                <div className="space-y-3">
                  {/* GE RJ45 Ports */}
                  {gePorts.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">GE RJ45 ({gePorts.length})</p>
                      <div className="flex flex-wrap gap-2">
                        {gePorts.map((port) => (
                          <PortIcon
                            key={`ge-${port.port_number}`}
                            type="ge"
                            number={port.port_number}
                            status={port.status}
                            isUplink={true}
                            label={port.label}
                            onClick={() => handlePortClick('ge', port.port_number)}
                            onEdit={() => handleEditPort(port.port_number, port.label)}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* SFP Ports */}
                  {sfpPorts.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">SFP ({sfpPorts.length})</p>
                      <div className="flex flex-wrap gap-2">
                        {sfpPorts.map((port) => (
                          <PortIcon
                            key={`sfp-${port.port_number}`}
                            type="sfp"
                            number={port.port_number}
                            status={port.status}
                            isUplink={true}
                            label={port.label}
                            onClick={() => handlePortClick('sfp', port.port_number)}
                            onEdit={() => handleEditPort(port.port_number, port.label)}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 10G SFP+ Ports */}
                  {xgePorts.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">10G SFP+ ({xgePorts.length})</p>
                      <div className="flex flex-wrap gap-2">
                        {xgePorts.map((port) => (
                          <PortIcon
                            key={`xge-${port.port_number}`}
                            type="xge"
                            number={port.port_number}
                            status={port.status}
                            isUplink={true}
                            label={port.label}
                            onClick={() => handlePortClick('xge', port.port_number)}
                            onEdit={() => handleEditPort(port.port_number, port.label)}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Fallback if no uplink data */}
                  {gePorts.length === 0 && sfpPorts.length === 0 && xgePorts.length === 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">Uplink Ports</p>
                      <div className="flex flex-wrap gap-2">
                        {uplinkPorts.map((port) => (
                          <PortIcon
                            key={`${port.port_type}-${port.port_number}`}
                            type={port.port_type}
                            number={port.port_number}
                            status={port.status}
                            isUplink={true}
                            onClick={() => handlePortClick(port.port_type, port.port_number)}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Legend */}
                <div className="mt-3 pt-3 border-t border-gray-700 flex items-center gap-4 text-xs text-gray-400">
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 bg-green-500 rounded"></span> PON Online
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 bg-blue-500 rounded"></span> Uplink Online
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 bg-gray-400 rounded"></span> Offline
                  </span>
                </div>
              </>
            )}
          </div>
        )}

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
          <>
            <button
              onClick={(e) => { e.stopPropagation(); onEdit && onEdit(olt); }}
              className="px-3 py-1.5 text-sm text-[#2563eb] border border-[#e8eaed] bg-white rounded-lg hover:bg-blue-50 font-medium transition-all duration-150 flex items-center gap-1.5"
              title="Edit OLT"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Edit
            </button>
            <button
              onClick={handleDelete}
              className="px-3 py-1.5 text-sm text-[#dc2626] border border-[#e8eaed] bg-white rounded-lg hover:bg-red-50 font-medium transition-all duration-150"
            >
              Delete
            </button>
          </>
        )}
      </div>

      {/* Port Description Edit Modal */}
      {editingPort && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={(e) => { e.stopPropagation(); setEditingPort(null); }}
        >
          <div
            className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Edit Port GE{editingPort} Description
            </h3>
            <p className="text-sm text-gray-500 mb-4">
              Set a custom name for this port. This will be synced to the OLT.
            </p>
            <input
              type="text"
              value={portDescription}
              onChange={(e) => setPortDescription(e.target.value)}
              placeholder="Enter port description (e.g., MIKROTIK, ROUTER)"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 mb-4"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSavePortDescription();
                if (e.key === 'Escape') setEditingPort(null);
              }}
            />
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setEditingPort(null)}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleSavePortDescription}
                disabled={savingPort}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50 flex items-center gap-2"
              >
                {savingPort ? (
                  <>
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                    Saving...
                  </>
                ) : 'Save to OLT'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ONU Table Component - Enterprise Pro Design
function ONUTable({ onus, onEdit, onDelete, onReboot, isAdmin, trafficData, onGraph }) {
  const darkMode = useContext(DarkModeContext);
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
      <div className={`rounded-xl border p-12 text-center ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-[#e8eaed]'}`}>
        <div className={`w-14 h-14 rounded-lg flex items-center justify-center mx-auto mb-4 ${darkMode ? 'bg-slate-700' : 'bg-[#f4f5f7]'}`}>
          <svg className={`w-7 h-7 ${darkMode ? 'text-slate-400' : 'text-[#9ca3af]'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
          </svg>
        </div>
        <p className={`font-medium ${darkMode ? 'text-white' : 'text-[#111827]'}`}>No ONUs found</p>
        <p className={`text-sm mt-1 ${darkMode ? 'text-slate-400' : 'text-[#9ca3af]'}`}>Try adjusting your filters or search query</p>
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
      <div className={`rounded-xl border overflow-hidden ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-[#e8eaed]'}`}>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className={`border-b ${darkMode ? 'bg-slate-700 border-slate-600' : 'bg-[#f4f5f7] border-[#e8eaed]'}`}>
                <th className={`px-3 py-2.5 text-left text-sm font-semibold uppercase tracking-wider ${darkMode ? 'text-slate-300' : 'text-[#4b5563]'}`}>OLT</th>
                <th className={`px-3 py-2.5 text-left text-sm font-semibold uppercase tracking-wider ${darkMode ? 'text-slate-300' : 'text-[#4b5563]'}`} title="PON Port / ONU ID">PON</th>
                <th className={`px-3 py-2.5 text-left text-sm font-semibold uppercase tracking-wider ${darkMode ? 'text-slate-300' : 'text-[#4b5563]'}`}>Customer</th>
                <th className={`px-3 py-2.5 text-left text-sm font-semibold uppercase tracking-wider ${darkMode ? 'text-slate-300' : 'text-[#4b5563]'}`}>MAC</th>
                <th className={`px-2 py-2.5 text-left text-sm font-semibold uppercase tracking-wider ${darkMode ? 'text-slate-300' : 'text-[#4b5563]'}`}>Model</th>
                <th className={`px-3 py-2.5 text-center text-sm font-semibold uppercase tracking-wider ${darkMode ? 'text-slate-300' : 'text-[#4b5563]'}`}>BW</th>
                <th className={`px-3 py-2.5 text-center text-sm font-semibold uppercase tracking-wider ${darkMode ? 'text-slate-300' : 'text-[#4b5563]'}`}>Dist</th>
                <th className={`px-3 py-2.5 text-center text-sm font-semibold uppercase tracking-wider ${darkMode ? 'text-slate-300' : 'text-[#4b5563]'}`} title="ONU RX/TX Power, Temperature, Voltage, TX Bias">OPM</th>
                <th className={`px-2 py-2.5 text-center text-sm font-semibold uppercase tracking-wider ${darkMode ? 'text-slate-300' : 'text-[#4b5563]'}`}></th>
              </tr>
            </thead>
            <tbody className={`divide-y ${darkMode ? 'divide-slate-700' : 'divide-[#e8eaed]'}`}>
              {onus.map((onu) => {
                const images = onu.image_urls || (onu.image_url ? [onu.image_url] : []);
                const hasImages = images.length > 0;
                return (
                  <tr key={onu.id} className={`transition-colors duration-150 group ${darkMode ? 'hover:bg-slate-700/50' : 'hover:bg-blue-50/50'}`}>
                    {/* OLT Name */}
                    <td className="px-3 py-2 whitespace-nowrap">
                      <span className={`text-base font-medium ${darkMode ? 'text-white' : 'text-gray-800'}`}>{onu.olt_name}</span>
                    </td>
                    {/* PON/ONU with MAC on hover, status dot */}
                    <td className="px-3 py-2 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className={`w-3 h-3 rounded-full ${onu.is_online ? 'bg-green-500' : 'bg-red-500'}`}></span>
                        <span className={`text-base font-mono ${darkMode ? 'text-slate-300' : 'text-gray-700'}`} title={`MAC: ${onu.mac_address}${onu.model ? ` | Model: ${onu.model}` : ''}`}>
                          {onu.pon_port}:{onu.onu_id}
                        </span>
                      </div>
                    </td>
                    {/* Customer with region, location, photo icons */}
                    <td className="px-3 py-2 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <div className="min-w-0 flex-1">
                          <span className={`text-base font-medium truncate block max-w-[180px] ${darkMode ? 'text-white' : 'text-gray-800'}`} title={onu.description || 'No name'}>
                            {onu.description || <span className="text-gray-400 italic">-</span>}
                          </span>
                          {onu.region_name && (
                            <span className="text-sm font-medium truncate block max-w-[150px]" style={{ color: onu.region_color || '#6366F1' }} title={onu.region_name}>{onu.region_name}</span>
                          )}
                        </div>
                        {/* Photo icon */}
                        {hasImages && (
                          <button onClick={() => openPreview(onu)} className="p-1 text-blue-500 hover:text-blue-700" title={`${images.length} photo(s)`}>
                            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" clipRule="evenodd" /></svg>
                          </button>
                        )}
                        {/* Location icon */}
                        {onu.latitude && onu.longitude && (
                          <button onClick={() => window.open(`https://www.google.com/maps?q=${onu.latitude},${onu.longitude}`, '_blank')} className="p-1 text-emerald-500 hover:text-emerald-700" title="Map">
                            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" /></svg>
                          </button>
                        )}
                      </div>
                    </td>
                    {/* MAC Address */}
                    <td className="px-3 py-2 whitespace-nowrap">
                      <span className={`text-sm font-mono ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                        {onu.mac_address}
                      </span>
                    </td>
                    {/* Model */}
                    <td className="px-2 py-2 whitespace-nowrap">
                      <span className={`text-xs font-medium ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                        {onu.model || '-'}
                      </span>
                    </td>
                    {/* BW - Traffic */}
                    <td className="px-3 py-2 whitespace-nowrap text-center">
                      {(() => {
                        const traffic = trafficMap[onu.mac_address];
                        if (!traffic) return <span className="text-gray-300 text-sm">-</span>;
                        const rx = traffic.rx_kbps || 0;
                        const tx = traffic.tx_kbps || 0;
                        return (
                          <div className="flex items-center justify-center gap-1.5 text-sm">
                            <span className={`font-semibold ${rx > 10000 ? 'text-green-600' : 'text-gray-600'}`}>↓{rx > 1000 ? `${(rx/1000).toFixed(0)}M` : `${rx.toFixed(0)}K`}</span>
                            <span className={`font-semibold ${tx > 10000 ? 'text-blue-600' : 'text-gray-600'}`}>↑{tx > 1000 ? `${(tx/1000).toFixed(0)}M` : `${tx.toFixed(0)}K`}</span>
                          </div>
                        );
                      })()}
                    </td>
                    {/* Distance */}
                    <td className="px-3 py-2 whitespace-nowrap text-center">
                      {onu.distance ? (
                        <span className="text-sm font-semibold text-blue-600">{onu.distance >= 1000 ? `${(onu.distance/1000).toFixed(1)}k` : onu.distance}m</span>
                      ) : (
                        <span className="text-gray-300 text-sm">-</span>
                      )}
                    </td>
                    {/* OPM - ONU optical data */}
                    <td className="px-3 py-2 whitespace-nowrap">
                      <div className="flex flex-col text-sm leading-relaxed">
                        <div className="flex items-center gap-1.5" title="ONU RX / TX Power">
                          <span className="text-gray-500">Rx</span>
                          {onu.onu_rx_power ? (
                            <span className={`font-semibold ${onu.onu_rx_power < -20 ? 'text-red-600' : onu.onu_rx_power < -15 ? 'text-amber-600' : 'text-emerald-600'}`}>
                              {onu.onu_rx_power.toFixed(1)}
                            </span>
                          ) : <span className="text-gray-300">-</span>}
                          <span className="text-gray-500">Tx</span>
                          {onu.onu_tx_power ? (
                            <span className="font-semibold text-blue-600">{onu.onu_tx_power.toFixed(1)}</span>
                          ) : <span className="text-gray-300">-</span>}
                        </div>
                        <div className="flex items-center gap-1.5 text-gray-500" title="Temp / Volt / Bias">
                          {onu.onu_temperature ? <span className={onu.onu_temperature > 50 ? 'text-red-600' : 'text-teal-600'}>{onu.onu_temperature.toFixed(0)}°</span> : <span className="text-gray-300">-</span>}
                          {onu.onu_voltage ? <span className="text-purple-600">{onu.onu_voltage.toFixed(1)}V</span> : ''}
                          {onu.onu_tx_bias ? <span className="text-pink-600">{onu.onu_tx_bias.toFixed(0)}mA</span> : ''}
                        </div>
                      </div>
                    </td>
                    {/* Actions - Icon buttons */}
                    <td className="px-2 py-2 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        <button onClick={() => onGraph && onGraph('onu', onu.id, onu.description || onu.mac_address)} className="p-2 text-purple-600 hover:bg-purple-50 rounded" title="Traffic Graph">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                        </button>
                        <button onClick={() => onEdit(onu)} className="p-2 text-blue-600 hover:bg-blue-50 rounded" title="Edit">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                        </button>
                        <button onClick={() => window.confirm(`Reboot "${onu.description || onu.mac_address}"?`) && onReboot(onu.id)} className="p-2 text-amber-600 hover:bg-amber-50 rounded" title="Reboot">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                        </button>
                        {isAdmin && (
                          <button onClick={() => window.confirm('Delete?') && onDelete(onu.id)} className="p-2 text-red-600 hover:bg-red-50 rounded" title="Delete">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
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
function ONUCard({ onu, onEdit, onDelete, onReboot, isAdmin, onImagePreview }) {
  const darkMode = useContext(DarkModeContext);
  const images = onu.image_urls || (onu.image_url ? [onu.image_url] : []);
  const hasImages = images.length > 0;

  return (
    <div className={`rounded-2xl shadow-material-1 p-4 mb-4 border relative overflow-hidden ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-100'}`}>
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
      <div className="grid grid-cols-3 gap-2 text-sm mb-3">
        <div className="bg-gradient-to-br from-slate-50 to-slate-100 rounded-xl p-2.5 border border-slate-200/50">
          <span className="text-slate-500 text-xs">OLT</span>
          <p className="font-semibold text-slate-700">{onu.olt_name}</p>
        </div>
        <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 rounded-xl p-2.5 border border-indigo-200/50">
          <span className="text-indigo-500 text-xs">Port</span>
          <p className="font-semibold font-mono text-indigo-700">0/{onu.pon_port}:{onu.onu_id}</p>
        </div>
        <div className="bg-gradient-to-br from-violet-50 to-violet-100 rounded-xl p-2.5 border border-violet-200/50">
          <span className="text-violet-500 text-xs">Model</span>
          <p className="font-semibold text-violet-700">{onu.model || '-'}</p>
        </div>
        <div className="bg-gradient-to-br from-cyan-50 to-cyan-100 rounded-xl p-2.5 border border-cyan-200/50">
          <span className="text-cyan-500 text-xs">Distance</span>
          <p className="font-semibold text-cyan-700">{onu.distance ? `${onu.distance}m` : '-'}</p>
        </div>
        <div className={`rounded-xl p-2.5 border ${onu.rx_power ? (!onu.is_online ? 'bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200/50' : onu.rx_power < -25 ? 'bg-gradient-to-br from-red-50 to-red-100 border-red-200/50' : onu.rx_power < -20 ? 'bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200/50' : 'bg-gradient-to-br from-emerald-50 to-emerald-100 border-emerald-200/50') : 'bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200/50'}`}>
          <span className={`text-xs ${onu.rx_power ? (!onu.is_online ? 'text-gray-400' : onu.rx_power < -25 ? 'text-red-500' : onu.rx_power < -20 ? 'text-amber-500' : 'text-emerald-500') : 'text-gray-400'}`}>OLT RX</span>
          <p className={`font-semibold ${onu.rx_power ? (!onu.is_online ? 'text-gray-400 italic' : onu.rx_power < -25 ? 'text-red-700' : onu.rx_power < -20 ? 'text-amber-700' : 'text-emerald-700') : 'text-gray-400'}`} title={onu.rx_power && !onu.is_online ? 'Last known value (ONU offline)' : 'OLT-measured RX power'}>
            {onu.rx_power ? `${onu.rx_power.toFixed(2)} dBm${!onu.is_online ? ' *' : ''}` : '-'}
          </p>
        </div>
        <div className={`rounded-xl p-2.5 border ${onu.onu_rx_power ? (!onu.is_online ? 'bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200/50' : onu.onu_rx_power < -20 ? 'bg-gradient-to-br from-red-50 to-red-100 border-red-200/50' : onu.onu_rx_power < -15 ? 'bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200/50' : 'bg-gradient-to-br from-emerald-50 to-emerald-100 border-emerald-200/50') : 'bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200/50'}`}>
          <span className={`text-xs ${onu.onu_rx_power ? (!onu.is_online ? 'text-gray-400' : onu.onu_rx_power < -20 ? 'text-red-500' : onu.onu_rx_power < -15 ? 'text-amber-500' : 'text-emerald-500') : 'text-gray-400'}`}>ONU RX</span>
          <p className={`font-semibold ${onu.onu_rx_power ? (!onu.is_online ? 'text-gray-400 italic' : onu.onu_rx_power < -20 ? 'text-red-700' : onu.onu_rx_power < -15 ? 'text-amber-700' : 'text-emerald-700') : 'text-gray-400'}`} title={onu.onu_rx_power && !onu.is_online ? 'Last known value (ONU offline)' : 'ONU self-reported RX power'}>
            {onu.onu_rx_power ? `${onu.onu_rx_power.toFixed(2)} dBm${!onu.is_online ? ' *' : ''}` : '-'}
          </p>
        </div>
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-2.5 border border-blue-200/50">
          <span className="text-blue-500 text-xs">TX Power</span>
          <p className="font-semibold text-blue-700">{onu.onu_tx_power ? `${onu.onu_tx_power.toFixed(2)} dBm` : '-'}</p>
        </div>
        <div className={`rounded-xl p-2.5 border ${onu.onu_temperature ? (onu.onu_temperature > 50 ? 'bg-gradient-to-br from-red-50 to-red-100 border-red-200/50' : onu.onu_temperature > 40 ? 'bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200/50' : 'bg-gradient-to-br from-teal-50 to-teal-100 border-teal-200/50') : 'bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200/50'}`}>
          <span className={`text-xs ${onu.onu_temperature ? (onu.onu_temperature > 50 ? 'text-red-500' : onu.onu_temperature > 40 ? 'text-amber-500' : 'text-teal-500') : 'text-gray-400'}`}>Temp</span>
          <p className={`font-semibold ${onu.onu_temperature ? (onu.onu_temperature > 50 ? 'text-red-700' : onu.onu_temperature > 40 ? 'text-amber-700' : 'text-teal-700') : 'text-gray-400'}`}>{onu.onu_temperature ? `${onu.onu_temperature.toFixed(1)}°C` : '-'}</p>
        </div>
        <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-2.5 border border-purple-200/50">
          <span className="text-purple-500 text-xs">Voltage</span>
          <p className="font-semibold text-purple-700">{onu.onu_voltage ? `${onu.onu_voltage.toFixed(2)}V` : '-'}</p>
        </div>
        <div className="bg-gradient-to-br from-pink-50 to-pink-100 rounded-xl p-2.5 border border-pink-200/50">
          <span className="text-pink-500 text-xs">TX Bias</span>
          <p className="font-semibold text-pink-700">{onu.onu_tx_bias ? `${onu.onu_tx_bias.toFixed(2)}mA` : '-'}</p>
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
          <button
            onClick={() => {
              if (window.confirm(`Reboot ONU "${onu.description || onu.mac_address}"?`)) onReboot(onu.id);
            }}
            className="px-3 py-1.5 text-sm bg-amber-500 text-white rounded-lg font-medium shadow-sm hover:bg-amber-600 transition-colors"
          >
            Reboot
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

  // Loading state for API
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // Multiple diagrams support - now loaded from API
  const [diagrams, setDiagrams] = useState([]);
  const [currentDiagramId, setCurrentDiagramId] = useState(null);

  // Debounce ref for auto-save
  const saveTimeoutRef = useRef(null);
  const pendingSaveRef = useRef(false);

  // Load diagrams from API on mount
  useEffect(() => {
    const loadDiagrams = async () => {
      try {
        setLoading(true);
        setLoadError(null);
        const response = await api.getDiagrams();
        const apiDiagrams = response.data.diagrams || [];

        if (apiDiagrams.length === 0) {
          // No diagrams exist, create a default one
          const newDiagramResp = await api.createDiagram({
            name: 'Diagram 1',
            nodes: '[]',
            connections: '[]',
            settings: JSON.stringify({ oltPower: 5, onuSensitivity: -28 }),
            is_shared: false
          });
          const newDiagram = newDiagramResp.data;
          setDiagrams([{
            id: newDiagram.id,
            name: newDiagram.name,
            nodes: JSON.parse(newDiagram.nodes || '[]'),
            connections: JSON.parse(newDiagram.connections || '[]'),
            settings: JSON.parse(newDiagram.settings || '{}'),
            is_shared: newDiagram.is_shared,
            owner_id: newDiagram.owner_id,
            owner_name: newDiagram.owner_name
          }]);
          setCurrentDiagramId(newDiagram.id);
        } else {
          // Parse JSON fields from API response
          const parsedDiagrams = apiDiagrams.map(d => ({
            id: d.id,
            name: d.name,
            nodes: JSON.parse(d.nodes || '[]'),
            connections: JSON.parse(d.connections || '[]'),
            settings: JSON.parse(d.settings || '{}'),
            is_shared: d.is_shared,
            owner_id: d.owner_id,
            owner_name: d.owner_name
          }));
          setDiagrams(parsedDiagrams);
          // Set current diagram to the first one (most recently updated)
          setCurrentDiagramId(parsedDiagrams[0].id);
        }
      } catch (err) {
        console.error('Failed to load diagrams:', err);
        setLoadError('Failed to load diagrams. Please refresh the page.');
        // Fallback to localStorage for offline support
        try {
          const saved = localStorage.getItem('splitterDiagrams');
          if (saved) {
            const localDiagrams = JSON.parse(saved);
            setDiagrams(localDiagrams);
            setCurrentDiagramId(localDiagrams[0]?.id || 'default');
          }
        } catch (e) {}
      } finally {
        setLoading(false);
      }
    };
    loadDiagrams();
  }, []);

  const [showDiagramMenu, setShowDiagramMenu] = useState(false);
  const [editingDiagramName, setEditingDiagramName] = useState(null);
  const [newDiagramName, setNewDiagramName] = useState('');

  // Get current diagram
  const currentDiagram = diagrams.find(d => d.id === currentDiagramId) || diagrams[0] || null;

  // Nodes and connections from current diagram
  const [nodes, setNodes] = useState([]);
  const [connections, setConnections] = useState([]);

  // Update nodes/connections when switching diagrams
  useEffect(() => {
    const diagram = diagrams.find(d => d.id === currentDiagramId);
    if (diagram) {
      setNodes(diagram.nodes || []);
      setConnections(diagram.connections || []);
      setOltPower(diagram.settings?.oltPower || 5);
      setOnuSensitivity(diagram.settings?.onuSensitivity || -28);
    }
  }, [currentDiagramId, diagrams]);

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
  const createNewDiagram = async () => {
    try {
      setSaveStatus('saving');
      const response = await api.createDiagram({
        name: `Diagram ${diagrams.length + 1}`,
        nodes: '[]',
        connections: '[]',
        settings: JSON.stringify({ oltPower: 5, onuSensitivity: -28 }),
        is_shared: false
      });
      const newDiagram = response.data;
      const parsedDiagram = {
        id: newDiagram.id,
        name: newDiagram.name,
        nodes: JSON.parse(newDiagram.nodes || '[]'),
        connections: JSON.parse(newDiagram.connections || '[]'),
        settings: JSON.parse(newDiagram.settings || '{}'),
        is_shared: newDiagram.is_shared,
        owner_id: newDiagram.owner_id,
        owner_name: newDiagram.owner_name
      };
      setDiagrams([...diagrams, parsedDiagram]);
      setCurrentDiagramId(newDiagram.id);
      setNodes([]);
      setConnections([]);
      setShowDiagramMenu(false);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (err) {
      console.error('Failed to create diagram:', err);
      setSaveStatus('error');
      alert('Failed to create diagram');
    }
  };

  // Rename diagram
  const renameDiagram = async (id, newName) => {
    try {
      await api.updateDiagram(id, { name: newName });
      setDiagrams(diagrams.map(d => d.id === id ? { ...d, name: newName } : d));
      setEditingDiagramName(null);
    } catch (err) {
      console.error('Failed to rename diagram:', err);
      alert('Failed to rename diagram');
    }
  };

  // Delete diagram
  const handleDeleteDiagram = async (id) => {
    if (diagrams.length <= 1) {
      alert('Cannot delete the last diagram');
      return;
    }
    if (window.confirm('Delete this diagram?')) {
      try {
        await api.deleteDiagram(id);
        const newDiagrams = diagrams.filter(d => d.id !== id);
        setDiagrams(newDiagrams);
        if (currentDiagramId === id) {
          setCurrentDiagramId(newDiagrams[0].id);
        }
      } catch (err) {
        console.error('Failed to delete diagram:', err);
        alert('Failed to delete diagram');
      }
    }
  };

  // Switch diagram
  const switchDiagram = async (id) => {
    // Save current diagram first
    if (currentDiagramId && currentDiagram) {
      try {
        await api.updateDiagram(currentDiagramId, {
          nodes: JSON.stringify(nodes),
          connections: JSON.stringify(connections),
          settings: JSON.stringify({ oltPower, onuSensitivity })
        });
      } catch (err) {
        console.error('Failed to save current diagram:', err);
      }
    }
    const updatedDiagrams = diagrams.map(d =>
      d.id === currentDiagramId
        ? { ...d, nodes, connections, settings: { oltPower, onuSensitivity } }
        : d
    );
    setDiagrams(updatedDiagrams);
    setCurrentDiagramId(id);
    setShowDiagramMenu(false);
  };

  // Auto-save to API with debouncing whenever nodes, connections, or settings change
  useEffect(() => {
    // Skip if loading or no diagram selected
    if (loading || !currentDiagramId) return;

    // Clear any pending save timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Mark that we have pending changes
    pendingSaveRef.current = true;
    setSaveStatus('saving');

    // Debounce API save (500ms delay)
    saveTimeoutRef.current = setTimeout(async () => {
      if (!pendingSaveRef.current) return;

      try {
        await api.updateDiagram(currentDiagramId, {
          nodes: JSON.stringify(nodes),
          connections: JSON.stringify(connections),
          settings: JSON.stringify({ oltPower, onuSensitivity })
        });

        // Also update local state
        const updatedDiagrams = diagrams.map(d =>
          d.id === currentDiagramId
            ? { ...d, nodes, connections, settings: { oltPower, onuSensitivity } }
            : d
        );
        setDiagrams(updatedDiagrams);

        // Also save to localStorage as backup
        localStorage.setItem('splitterDiagrams', JSON.stringify(updatedDiagrams));

        setLastSaved(new Date());
        setSaveStatus('saved');
        pendingSaveRef.current = false;
        setTimeout(() => setSaveStatus('idle'), 2000);
      } catch (err) {
        console.error('Failed to auto-save diagram:', err);
        setSaveStatus('error');
        // Still save to localStorage as fallback
        const updatedDiagrams = diagrams.map(d =>
          d.id === currentDiagramId
            ? { ...d, nodes, connections, settings: { oltPower, onuSensitivity } }
            : d
        );
        localStorage.setItem('splitterDiagrams', JSON.stringify(updatedDiagrams));
      }
    }, 500);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [nodes, connections, oltPower, onuSensitivity, currentDiagramId, loading]);

  // Clear diagram function
  const clearDiagram = () => {
    if (window.confirm('Clear the current diagram? This cannot be undone.')) {
      setNodes([]);
      setConnections([]);
      setSelectedNode(null);
    }
  };

  // OLT and PON selection
  const [selectedOltId, setSelectedOltId] = useState(null);
  const [selectedPonPort, setSelectedPonPort] = useState(1);
  const [showOnuPicker, setShowOnuPicker] = useState(false);

  // Set default OLT when olts data loads
  useEffect(() => {
    if (olts.length > 0 && !selectedOltId) {
      setSelectedOltId(olts[0].id);
    }
  }, [olts, selectedOltId]);

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
      isOnline: onu.is_online,
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

  // Show loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading diagrams...</p>
        </div>
      </div>
    );
  }

  // Show error state
  if (loadError && diagrams.length === 0) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="text-red-500 text-4xl mb-4">!</div>
          <p className="text-red-600">{loadError}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

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
                            onClick={(e) => { e.stopPropagation(); handleDeleteDiagram(diagram.id); }}
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
            saveStatus === 'error' ? 'bg-red-100 border border-red-300' :
            'bg-gray-100 border border-gray-200'
          }`}>
            {saveStatus === 'saving' ? (
              <>
                <svg className="w-5 h-5 text-yellow-600 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span className="text-sm font-medium text-yellow-700">Saving to server...</span>
              </>
            ) : saveStatus === 'saved' ? (
              <>
                <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span className="text-sm font-medium text-green-700">Saved to server!</span>
              </>
            ) : saveStatus === 'error' ? (
              <>
                <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-sm font-medium text-red-700">Save failed (local backup)</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                </svg>
                <span className="text-sm font-medium text-gray-600">Cloud sync enabled</span>
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
              {node.type === 'onu' && (() => {
                // Get real-time online status from onus data
                const realOnu = node.onuId ? onus.find(o => o.id === node.onuId) : null;
                const isOnline = realOnu ? realOnu.is_online : (node.isOnline !== false);

                return (
                <div className={`relative h-full ${selectedNode?.id === node.id ? 'ring-2 ring-green-400 ring-offset-1' : ''}`}>
                  {/* ONU body - White plastic casing */}
                  <div className={`absolute inset-0 bg-gradient-to-b from-[#fefefe] to-[#f0f0f0] rounded shadow-md border ${!isOnline ? 'border-red-400' : 'border-[#ddd]'}`} style={{boxShadow: !isOnline ? '0 2px 8px rgba(239,68,68,0.3)' : '0 2px 6px rgba(0,0,0,0.1)'}}>
                    {/* Top brand strip - Red if offline, Blue if online */}
                    <div className={`absolute top-0 left-0 right-0 h-3 rounded-t flex items-center px-1.5 ${!isOnline ? 'bg-gradient-to-r from-red-700 via-red-500 to-red-700' : 'bg-gradient-to-r from-[#1e3a5f] via-[#2563eb] to-[#1e3a5f]'}`}>
                      <span className="text-[7px] font-bold text-white">ONU</span>
                      {!isOnline && <span className="text-[6px] text-red-200 ml-auto">OFFLINE</span>}
                    </div>

                    {/* Status LEDs - show online/offline status */}
                    <div className="absolute top-4 right-1.5 flex gap-1">
                      <div className={`w-1.5 h-1.5 rounded-full ${!isOnline ? 'bg-red-500' : powerMap[`${node.id}-rx`] !== undefined ? 'bg-green-500' : 'bg-gray-300'}`} style={!isOnline ? {boxShadow: '0 0 4px #ef4444'} : powerMap[`${node.id}-rx`] !== undefined ? {boxShadow: '0 0 4px #22c55e'} : {}}></div>
                      <div className={`w-1.5 h-1.5 rounded-full ${!isOnline ? 'bg-gray-400' : 'bg-blue-500'}`} style={isOnline ? {boxShadow: '0 0 4px #3b82f6'} : {}}></div>
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
                );
              })()}

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
function Sidebar({ currentPage, onNavigate, user, onLogout, isOpen, onClose, pageName, darkMode, onToggleDarkMode }) {
  const isAdmin = user?.role === 'admin';

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
    { id: 'onus', label: 'ONUs', icon: 'M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z' },
    { id: 'regions', label: 'Regions', icon: 'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z', adminOnly: false },
    { id: 'alarms', label: 'Alarms', icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' },
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
      <aside className={`fixed inset-y-0 left-0 z-50 w-[280px] border-r transform transition-all duration-300 ease-material lg:translate-x-0 lg:static lg:inset-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'} ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-[#e8eaed]'}`}>
        <div className="flex flex-col h-full">
          {/* Logo Section */}
          <div className={`p-6 border-b ${darkMode ? 'border-slate-700' : 'border-[#e8eaed]'}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#2563eb] rounded-lg flex items-center justify-center">
                  <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
                  </svg>
                </div>
                <div>
                  <h1 className={`text-base font-semibold ${darkMode ? 'text-white' : 'text-[#111827]'}`}>{pageName || 'OLT Manager'}</h1>
                  <p className={`text-xs ${darkMode ? 'text-slate-400' : 'text-[#9ca3af]'}`}>GPON Network</p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {/* Dark/Light Mode Toggle */}
                <button
                  onClick={onToggleDarkMode}
                  aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
                  title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
                  className={`p-2 rounded-lg transition-all duration-300 ${
                    darkMode
                      ? 'bg-yellow-100 text-yellow-600 hover:bg-yellow-200'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {darkMode ? (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" fill="none" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" fill="none" />
                    </svg>
                  )}
                </button>
                <button onClick={onClose} aria-label="Close menu" title="Close menu" className="lg:hidden p-2 text-[#9ca3af] hover:text-[#111827] hover:bg-[#f4f5f7] rounded-lg transition-colors">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
            <p className={`px-3 py-2 text-xs font-medium uppercase tracking-wider ${darkMode ? 'text-slate-400' : 'text-[#9ca3af]'}`}>Menu</p>
            {menuItems.map((item) => (
              <button
                key={item.id}
                onClick={() => { onNavigate(item.id); onClose(); }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 ${
                  currentPage === item.id
                    ? (darkMode ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-50 text-[#2563eb]')
                    : (darkMode ? 'text-slate-300 hover:bg-slate-700 hover:text-white' : 'text-[#4b5563] hover:bg-[#f4f5f7] hover:text-[#111827]')
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
          <div className={`p-4 border-t ${darkMode ? 'border-slate-700' : 'border-[#e8eaed]'}`}>
            <div className="flex items-center gap-3 mb-3">
              <div className="relative">
                <div className="w-10 h-10 bg-[#2563eb] rounded-lg flex items-center justify-center text-white font-semibold text-sm">
                  {user?.username?.[0]?.toUpperCase() || 'U'}
                </div>
                <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-[#059669] rounded-full border-2 ${darkMode ? 'border-slate-800' : 'border-white'}`}></div>
              </div>
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium truncate ${darkMode ? 'text-white' : 'text-[#111827]'}`}>{user?.full_name || user?.username}</p>
                <p className={`text-xs capitalize ${darkMode ? 'text-slate-400' : 'text-[#9ca3af]'}`}>{user?.role}</p>
              </div>
            </div>
            <button
              onClick={onLogout}
              className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg transition-all duration-150 border ${darkMode ? 'text-slate-300 hover:text-red-400 hover:bg-red-900/20 border-slate-600' : 'text-[#4b5563] hover:text-[#dc2626] hover:bg-red-50 border-[#e8eaed]'}`}
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

// License Overlay Component
function LicenseOverlay({ status, message }) {
  const getIcon = () => {
    switch (status) {
      case 'suspended': return '⚠️';
      case 'expired': return '⏰';
      case 'revoked': return '🚫';
      default: return '❌';
    }
  };

  const getTitle = () => {
    switch (status) {
      case 'suspended': return 'License Suspended';
      case 'expired': return 'License Expired';
      case 'revoked': return 'License Revoked';
      default: return 'License Invalid';
    }
  };

  const getBgColor = () => {
    switch (status) {
      case 'suspended': return 'from-yellow-600 to-orange-600';
      case 'expired': return 'from-red-600 to-red-800';
      case 'revoked': return 'from-gray-700 to-gray-900';
      default: return 'from-red-600 to-red-800';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm pointer-events-auto"></div>
      <div className={`relative bg-gradient-to-br ${getBgColor()} p-8 rounded-2xl shadow-2xl max-w-md mx-4 text-center pointer-events-auto`}>
        <div className="text-6xl mb-4">{getIcon()}</div>
        <h2 className="text-2xl font-bold text-white mb-4">{getTitle()}</h2>
        <p className="text-white/90 text-lg mb-6">{message}</p>
        <div className="bg-white/20 rounded-lg p-4">
          <p className="text-white/80 text-sm">
            Please contact your system administrator or support to resolve this issue.
          </p>
        </div>
        <div className="mt-6 text-white/60 text-xs">
          You can view the dashboard but all actions are disabled.
        </div>
      </div>
    </div>
  );
}

// Dashboard Component
function Dashboard({ user, onLogout, pageName }) {
  // Load saved page from localStorage, default to dashboard
  const [currentPage, setCurrentPage] = useState(() => {
    const savedPage = localStorage.getItem('currentPage');
    return savedPage || 'dashboard';
  });

  // License status
  const [licenseStatus, setLicenseStatus] = useState({ status: 'active', message: null });
  const [licenseInfo, setLicenseInfo] = useState(null);
  const licenseCheckRef = useRef(null);

  // Update notification
  const [updateInfo, setUpdateInfo] = useState(null);

  // Fetch license status and check for updates
  const fetchLicenseStatus = useCallback(async () => {
    try {
      const response = await api.getLicenseInfo();
      const data = response.data;
      setLicenseStatus({
        status: data.status || 'active',
        message: data.status_message
      });
      // Store full license info for Settings modal
      setLicenseInfo(data);
    } catch (error) {
      console.error('Failed to fetch license status:', error);
    }

    // Check for updates
    try {
      const updateResponse = await api.checkForUpdates();
      if (updateResponse.data.update_available && updateResponse.data.update) {
        setUpdateInfo(updateResponse.data);
      }
    } catch (error) {
      // Silently fail update check
    }
  }, []);

  // Check license on mount and every 60 seconds
  useEffect(() => {
    fetchLicenseStatus();
    licenseCheckRef.current = setInterval(fetchLicenseStatus, 60000);
    return () => {
      if (licenseCheckRef.current) {
        clearInterval(licenseCheckRef.current);
      }
    };
  }, [fetchLicenseStatus]);

  const isLicenseValid = licenseStatus.status === 'active';

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
  const [alarmSettings, setAlarmSettings] = useState({
    new_onu_registration: true,
    onu_offline: true,
    onu_back_online: true,
    olt_offline: true,
    olt_back_online: true,
    weak_signal: false,
    weak_signal_threshold: -25,
    weak_signal_lower_threshold: -30,
    high_temperature: false,
    high_temperature_threshold: 60,
    selected_onus: [],
    selected_regions: [],
    quiet_hours_enabled: false,
    quiet_hours_start: '22:00',
    quiet_hours_end: '07:00'
  });
  const [alarmSaving, setAlarmSaving] = useState(false);
  const [selectedOLT, setSelectedOLT] = useState(null);
  const [selectedRegion, setSelectedRegion] = useState(null);
  const [selectedPonPort, setSelectedPonPort] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showOfflineOnly, setShowOfflineOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showAddOLTModal, setShowAddOLTModal] = useState(false);
  const [showEditOLTModal, setShowEditOLTModal] = useState(false);
  const [editingOLT, setEditingOLT] = useState(null);
  const [showEditONUModal, setShowEditONUModal] = useState(false);
  const [showRegionModal, setShowRegionModal] = useState(false);
  const [showUserModal, setShowUserModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [settingsDefaultTab, setSettingsDefaultTab] = useState('general');
  const [showTrafficGraphModal, setShowTrafficGraphModal] = useState(false);
  const [graphEntity, setGraphEntity] = useState({ type: null, id: null, name: '' });
  const [editingONU, setEditingONU] = useState(null);
  const [editingRegion, setEditingRegion] = useState(null);
  const [editingUser, setEditingUser] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  // Dark mode state with localStorage persistence
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode');
    return saved ? JSON.parse(saved) : false;
  });

  // Toggle dark mode and save to localStorage
  const toggleDarkMode = () => {
    setDarkMode(prev => {
      const newValue = !prev;
      localStorage.setItem('darkMode', JSON.stringify(newValue));
      return newValue;
    });
  };
  const [mobilePreviewImages, setMobilePreviewImages] = useState(null);
  const [mobilePreviewTitle, setMobilePreviewTitle] = useState('');
  const [trafficData, setTrafficData] = useState(null);
  const [trafficLoading, setTrafficLoading] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);
  const wsMapRef = useRef({});  // Map of OLT ID -> WebSocket for "All" mode
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

  const fetchONUs = useCallback(async (searchTerm = null) => {
    try {
      let response;
      const params = {};
      if (searchTerm) {
        response = await api.searchONUs(searchTerm);
      } else {
        if (selectedOLT) params.olt_id = selectedOLT;
        if (selectedRegion) params.region_id = selectedRegion;
        response = await api.getONUs(params);
      }
      setONUs(response.data.onus);
    } catch (error) {
      console.error('Failed to fetch ONUs:', error);
    }
  }, [selectedOLT, selectedRegion]);

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

  const fetchAlarmSettings = useCallback(async () => {
    try {
      const response = await api.getAlarmSettings();
      setAlarmSettings(response.data);
    } catch (error) {
      console.error('Failed to fetch alarm settings:', error);
    }
  }, []);

  const handleSaveAlarmSettings = async () => {
    setAlarmSaving(true);
    try {
      await api.updateAlarmSettings(alarmSettings);
      alert('Alarm settings saved successfully!');
    } catch (error) {
      console.error('Failed to save alarm settings:', error);
      alert('Failed to save alarm settings: ' + (error.response?.data?.detail || error.message));
    } finally {
      setAlarmSaving(false);
    }
  };

  // Helper function to get WebSocket URL
  const getWsUrl = useCallback((oltId) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const apiUrl = process.env.REACT_APP_API_URL || '';
    let wsHost = window.location.host;

    if (apiUrl) {
      try {
        const url = new URL(apiUrl);
        wsHost = url.host;
      } catch (e) {
        console.error('Invalid API URL:', apiUrl);
      }
    }

    return `${protocol}//${wsHost}/ws/traffic/${oltId}`;
  }, []);

  // WebSocket connection for live traffic (single OLT)
  const connectWebSocket = useCallback((oltId) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const wsUrl = getWsUrl(oltId);
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
  }, [getWsUrl]);

  // Connect to all OLTs WebSockets for "All" mode
  const connectAllWebSockets = useCallback((oltList) => {
    // Check if already connected to all OLTs
    const currentIds = Object.keys(wsMapRef.current).map(Number).sort();
    const newIds = oltList.map(o => o.id).sort();
    if (JSON.stringify(currentIds) === JSON.stringify(newIds) && Object.values(wsMapRef.current).some(ws => ws.readyState === WebSocket.OPEN)) {
      console.log('Already connected to all OLTs, skipping reconnect');
      return;
    }

    // Close existing connections
    Object.values(wsMapRef.current).forEach(ws => ws.close());
    wsMapRef.current = {};
    trafficBufferRef.current = {};
    setTrafficLoading(true);

    console.log('Initiating WebSocket connections to', oltList.length, 'OLTs');

    oltList.forEach(olt => {
      const wsUrl = getWsUrl(olt.id);
      console.log('Connecting to WebSocket for OLT', olt.name, ':', wsUrl);

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected for OLT', olt.name);
        setWsConnected(true);
        setTrafficLoading(false);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Merge traffic data from this OLT into the global buffer
          if (data.traffic && data.traffic.length > 0) {
            data.traffic.forEach(t => {
              trafficBufferRef.current[t.mac_address] = {
                ...t,
                olt_id: olt.id,
                olt_name: olt.name,
                lastUpdate: Date.now()
              };
            });
          }

          // Create merged traffic array from all OLTs
          const mergedTraffic = Object.values(trafficBufferRef.current)
            .filter(t => Date.now() - t.lastUpdate < 30000)
            .sort((a, b) => (b.rx_kbps + b.tx_kbps) - (a.rx_kbps + a.tx_kbps));

          setTrafficData({
            olt_id: 'all',
            timestamp: new Date().toISOString(),
            traffic: mergedTraffic
          });
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error for OLT', olt.name, ':', error);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected for OLT', olt.name);
        delete wsMapRef.current[olt.id];
        // Check if all connections are closed
        if (Object.keys(wsMapRef.current).length === 0) {
          setWsConnected(false);
        }
      };

      wsMapRef.current[olt.id] = ws;
    });
  }, [getWsUrl]);

  // Disconnect all WebSockets
  const disconnectAllWebSockets = useCallback(() => {
    // Close single OLT connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    // Close all OLT connections
    Object.values(wsMapRef.current).forEach(ws => ws.close());
    wsMapRef.current = {};
    setTrafficData(null);
    setWsConnected(false);
    trafficBufferRef.current = {};
  }, []);

  // Connect/disconnect WebSocket when OLT is selected on ONUs page
  useEffect(() => {
    console.log('WebSocket effect triggered:', { currentPage, selectedOLT, oltsCount: olts.length });

    if (currentPage !== 'onus') {
      // Close all WebSockets if not on ONUs page
      console.log('Not on ONUs page, closing connections');
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      Object.values(wsMapRef.current).forEach(ws => ws.close());
      wsMapRef.current = {};
      setTrafficData(null);
      setWsConnected(false);
      trafficBufferRef.current = {};
      return;
    }

    if (selectedOLT) {
      // Close all-OLT connections if any
      console.log('Connecting to single OLT:', selectedOLT);
      Object.values(wsMapRef.current).forEach(ws => ws.close());
      wsMapRef.current = {};
      // Connect to single OLT
      connectWebSocket(selectedOLT);
    } else {
      // "All" is selected - connect to all OLTs
      console.log('ALL selected, olts.length:', olts.length);
      if (olts.length > 0) {
        console.log('Connecting to ALL OLTs:', olts.map(o => o.name));
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
        connectAllWebSockets(olts);
      } else {
        console.log('No OLTs available yet, waiting...');
      }
    }
  }, [currentPage, selectedOLT, olts, connectWebSocket, connectAllWebSockets]);

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchStats(), fetchOLTs(), fetchONUs(), fetchRegions(), fetchUsers(), fetchSettings(), fetchAlarmSettings()]);
      setLoading(false);
    };
    loadData();
  }, [fetchStats, fetchOLTs, fetchONUs, fetchRegions, fetchUsers, fetchSettings, fetchAlarmSettings]);

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
    if (searchQuery.trim()) {
      fetchONUs(searchQuery.trim());
    } else {
      fetchONUs();
    }
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

  const handleEditOLT = (olt) => {
    setEditingOLT(olt);
    setShowEditOLTModal(true);
  };

  const handleUpdateOLT = async (id, data) => {
    await api.updateOLT(id, data);
    await fetchOLTs();
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

  const handleRebootONU = async (id) => {
    try {
      const response = await api.rebootONU(id);
      alert(response.data.message || 'Reboot command sent successfully');
    } catch (error) {
      alert('Failed to reboot ONU: ' + (error.response?.data?.detail || error.message));
    }
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
    <DarkModeContext.Provider value={darkMode}>
    <div className={`min-h-screen flex transition-colors duration-300 ${darkMode ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900' : 'bg-gradient-to-br from-gray-50 via-gray-100 to-gray-50'}`}>
      {/* License Status Overlay */}
      {!isLicenseValid && (
        <LicenseOverlay status={licenseStatus.status} message={licenseStatus.message} />
      )}

      <Sidebar
        currentPage={currentPage}
        onNavigate={setCurrentPage}
        user={user}
        onLogout={handleLogout}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        pageName={pageName}
        darkMode={darkMode}
        onToggleDarkMode={toggleDarkMode}
      />

      <div className={`flex-1 flex flex-col min-h-screen transition-colors duration-300 ${darkMode ? 'bg-slate-900' : 'bg-[#fafbfc]'}`}>
        {/* Header - Compact */}
        <header className={`sticky top-0 z-30 border-b transition-colors duration-300 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-[#e8eaed]'}`}>
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
              {/* Update Available Icon */}
              {updateInfo && updateInfo.update_available && (
                <button
                  onClick={() => {
                    setSettingsDefaultTab('license');
                    setShowSettingsModal(true);
                  }}
                  className="relative p-1.5 text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-all duration-150"
                  title={`Update available: v${updateInfo.update?.latest_version}`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse"></span>
                </button>
              )}
              <button
                onClick={() => {
                  setSettingsDefaultTab('general');
                  setShowSettingsModal(true);
                }}
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
              {/* OLTs Section - TOP OF PAGE */}
              <div className="mb-6">
                <div className="flex justify-between items-center mb-4">
                  <h2 className={`text-base font-semibold ${darkMode ? 'text-white' : 'text-[#111827]'}`}>OLTs</h2>
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
                  <div className={`rounded-xl border p-8 text-center ${darkMode ? 'bg-slate-800 border-slate-700 text-slate-400' : 'bg-white border-[#e8eaed] text-[#9ca3af]'}`}>
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
                        onEdit={handleEditOLT}
                        isSelected={selectedOLT === olt.id}
                        isAdmin={isAdmin}
                        onGraph={handleOpenGraph}
                        onPortGraph={(oltId, oltName, portType, portNumber) => {
                          handleOpenGraph('port', `${oltId}:${portType}:${portNumber}`, `${oltName} - ${portType.toUpperCase()} ${portNumber}`);
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>

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
                  <h2 className={`text-base font-semibold mb-4 ${darkMode ? 'text-white' : 'text-[#111827]'}`}>Regions</h2>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                    {regions.map((region) => (
                      <button
                        key={region.id}
                        onClick={() => handleSelectRegion(region.id)}
                        className={`rounded-xl p-4 text-left hover:shadow-sm transition-all duration-200 border ${darkMode ? 'bg-slate-800 border-slate-700 hover:bg-slate-700' : 'bg-white border-[#e8eaed]'}`}
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
                            <p className={`font-medium ${darkMode ? 'text-white' : 'text-[#111827]'}`}>{region.name}</p>
                            <p className="text-sm" style={{ color: region.color || '#6366F1' }}>{region.onu_count || 0} ONUs</p>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

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
                  <h2 className={`text-lg font-bold ${darkMode ? 'text-white' : 'text-gray-800'}`}>
                    ONUs
                    {selectedOLT && (
                      <span className={`text-sm font-normal ml-2 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                        ({olts.find((o) => o.id === selectedOLT)?.name})
                      </span>
                    )}
                    {selectedRegion && (
                      <span className={`text-sm font-normal ml-2 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                        ({regions.find((r) => r.id === selectedRegion)?.name})
                      </span>
                    )}
                    {selectedPonPort && (
                      <span className="text-sm font-normal text-emerald-600 ml-2">
                        - PON {selectedPonPort}
                      </span>
                    )}
                  </h2>
                  <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                    {(() => {
                      let count = selectedPonPort ? onus.filter(onu => onu.pon_port === selectedPonPort).length : onus.length;
                      if (showOfflineOnly) {
                        count = onus.filter(onu => (!selectedPonPort || onu.pon_port === selectedPonPort) && !onu.is_online).length;
                      }
                      return count;
                    })()} ONUs shown
                    {selectedPonPort && <span className="text-emerald-600"> (filtered by PON {selectedPonPort})</span>}
                    {showOfflineOnly && <span className="text-red-500"> (Offline Only)</span>}
                  </p>
                </div>
                <form onSubmit={handleSearch} className="flex gap-2 w-full sm:w-auto">
                  <input
                    type="text"
                    placeholder="Search by name or MAC..."
                    className={`flex-1 sm:w-64 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 ${darkMode ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-400' : 'bg-white border-gray-300'}`}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  <button type="submit" className={`px-4 py-2 rounded-lg ${darkMode ? 'bg-slate-700 text-slate-300 hover:bg-slate-600' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}>
                    Search
                  </button>
                  {(searchQuery || selectedOLT || selectedRegion || selectedPonPort || showOfflineOnly) && (
                    <button
                      type="button"
                      onClick={() => {
                        setSearchQuery('');
                        setSelectedOLT(null);
                        setSelectedRegion(null);
                        setSelectedPonPort(null);
                        setShowOfflineOnly(false);
                        fetchONUs();
                      }}
                      className={`px-4 py-2 rounded-lg ${darkMode ? 'bg-slate-700 text-slate-400 hover:bg-slate-600' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                    >
                      Clear
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setShowOfflineOnly(!showOfflineOnly)}
                    className={`px-4 py-2 rounded-lg font-medium transition ${
                      showOfflineOnly
                        ? 'bg-red-600 text-white hover:bg-red-700'
                        : darkMode
                          ? 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                  >
                    {showOfflineOnly ? 'Show All' : 'Show Offline'}
                  </button>
                </form>
              </div>

              {/* Filter by OLT buttons */}
              <div className="flex flex-wrap gap-2 mb-4">
                <button
                  onClick={() => {
                    console.log('All button clicked');
                    setSelectedOLT(null);
                    setSelectedRegion(null);
                    setSelectedPonPort(null);
                    // Directly connect to all OLTs
                    if (wsRef.current) {
                      wsRef.current.close();
                      wsRef.current = null;
                    }
                    if (olts.length > 0) {
                      console.log('Directly connecting to all OLTs:', olts.length);
                      connectAllWebSockets(olts);
                    }
                  }}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                    !selectedOLT && !selectedRegion ? 'bg-blue-600 text-white' : darkMode ? 'bg-slate-700 text-slate-300 hover:bg-slate-600' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  All
                </button>
                {olts.map((olt) => (
                  <button
                    key={olt.id}
                    onClick={() => handleSelectOLT(olt.id)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                      selectedOLT === olt.id ? 'bg-blue-600 text-white' : darkMode ? 'bg-slate-700 text-slate-300 hover:bg-slate-600' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
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
                    <span className={`text-sm font-medium ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>PON:</span>
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

              {/* Traffic Status Indicator - Shows for both "All" and specific OLT */}
              <div className="mb-4 flex items-center gap-3">
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${darkMode ? 'bg-slate-800 border-slate-600' : 'bg-gradient-to-r from-cyan-50 to-blue-50 border-cyan-200'}`}>
                  {trafficLoading ? (
                    <>
                      <svg className="animate-spin h-4 w-4 text-cyan-600" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span className={`text-sm font-medium ${darkMode ? 'text-cyan-400' : 'text-cyan-700'}`}>Updating traffic...</span>
                    </>
                  ) : (
                    <>
                      <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}></span>
                      <svg className={`w-4 h-4 ${darkMode ? 'text-cyan-400' : 'text-cyan-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                      </svg>
                      <span className={`text-sm font-medium ${darkMode ? 'text-cyan-400' : 'text-cyan-700'}`}>Live Traffic</span>
                      {!selectedOLT && <span className={`text-xs ${darkMode ? 'text-cyan-500' : 'text-cyan-600'}`}>(All OLTs)</span>}
                    </>
                  )}
                  <span className={`text-xs ${wsConnected ? 'text-green-600 font-medium' : darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                    {wsConnected ? (trafficData?.message ? `(${trafficData.message})` : '(Live ~3s)') : '(connecting...)'}
                  </span>
                </div>
                {trafficData && trafficData.timestamp && (
                  <span className={`text-xs ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                    {new Date(trafficData.timestamp).toLocaleTimeString()}
                  </span>
                )}
              </div>

              {(() => {
                let filteredOnus = selectedPonPort ? onus.filter(onu => onu.pon_port === selectedPonPort) : onus;
                // Apply offline filter if enabled
                if (showOfflineOnly) {
                  filteredOnus = filteredOnus.filter(onu => !onu.is_online);
                }
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
                        <ONUCard key={onu.id} onu={onu} onEdit={handleEditONU} onDelete={handleDeleteONU} onReboot={handleRebootONU} isAdmin={isAdmin} onImagePreview={handleMobileImagePreview} />
                      ))}
                    </div>
                  </>
                ) : (
                  <ONUTable onus={filteredOnus} onEdit={handleEditONU} onDelete={handleDeleteONU} onReboot={handleRebootONU} isAdmin={isAdmin} trafficData={trafficData && (selectedOLT ? trafficData.olt_id === selectedOLT : trafficData.olt_id === 'all') ? trafficData : null} onGraph={handleOpenGraph} />
                );
              })()}
            </>
          )}

          {/* Regions Page */}
          {currentPage === 'regions' && (
            <>
              <div className="flex justify-between items-center mb-4">
                <h2 className={`text-lg font-bold ${darkMode ? 'text-white' : 'text-gray-800'}`}>Regions</h2>
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
                  <div key={region.id} className={`rounded-xl shadow-md p-4 border-l-4 ${darkMode ? 'bg-slate-800' : 'bg-white'}`} style={{ borderLeftColor: region.color || '#3B82F6' }}>
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
                          <h3 className={`font-bold text-lg ${darkMode ? 'text-white' : 'text-gray-800'}`}>{region.name}</h3>
                          {region.description && <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>{region.description}</p>}
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

          {/* Alarms Page */}
          {currentPage === 'alarms' && (
            <div className="space-y-6">
              {/* Page Header */}
              <div className="flex justify-between items-center">
                <div>
                  <h2 className={`text-xl font-bold ${darkMode ? 'text-white' : 'text-gray-800'}`}>Alarm Settings</h2>
                  <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Configure WhatsApp notifications for different events</p>
                </div>
                <button
                  onClick={async () => {
                    setAlarmSaving(true);
                    try {
                      await api.updateAlarmSettings(alarmSettings);
                      alert('Alarm settings saved successfully!');
                    } catch (error) {
                      alert('Failed to save alarm settings');
                    }
                    setAlarmSaving(false);
                  }}
                  disabled={alarmSaving}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium disabled:opacity-50"
                >
                  {alarmSaving ? 'Saving...' : 'Save Settings'}
                </button>
              </div>

              {/* WhatsApp Status Check */}
              {!settings?.whatsapp_enabled && (
                <div className={`p-4 rounded-xl border ${darkMode ? 'bg-yellow-900/30 border-yellow-800' : 'bg-yellow-50 border-yellow-200'}`}>
                  <div className="flex items-center gap-3">
                    <svg className={`w-6 h-6 ${darkMode ? 'text-yellow-400' : 'text-yellow-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div>
                      <p className={`font-medium ${darkMode ? 'text-yellow-400' : 'text-yellow-800'}`}>WhatsApp Not Configured</p>
                      <p className={`text-sm ${darkMode ? 'text-yellow-300' : 'text-yellow-700'}`}>
                        Please enable WhatsApp and set recipient number in Settings to receive alarm notifications.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Alarm Categories Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                {/* Section 1: New ONU Registration */}
                <div className={`rounded-xl border p-5 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'}`}>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${darkMode ? 'bg-green-900/30' : 'bg-green-100'}`}>
                        <svg className={`w-6 h-6 ${darkMode ? 'text-green-400' : 'text-green-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
                        </svg>
                      </div>
                      <div>
                        <h3 className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>New ONU Registration</h3>
                        <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Alert when new ONU is detected</p>
                      </div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={alarmSettings.new_onu_registration}
                        onChange={(e) => setAlarmSettings({...alarmSettings, new_onu_registration: e.target.checked})}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                    </label>
                  </div>
                  <div className={`text-xs p-3 rounded-lg ${darkMode ? 'bg-slate-700/50 text-slate-300' : 'bg-gray-50 text-gray-600'}`}>
                    <p className="font-medium mb-1">Message includes:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li>ONU Name/MAC Address</li>
                      <li>Signal Strength (RX Power)</li>
                      <li>Distance from OLT</li>
                      <li>PON Port & OLT Name</li>
                    </ul>
                  </div>
                </div>

                {/* Section 2: ONU Offline/Lost */}
                <div className={`rounded-xl border p-5 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'}`}>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${darkMode ? 'bg-red-900/30' : 'bg-red-100'}`}>
                        <svg className={`w-6 h-6 ${darkMode ? 'text-red-400' : 'text-red-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                        </svg>
                      </div>
                      <div>
                        <h3 className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>ONU Offline / Lost</h3>
                        <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Alert when ONU goes offline</p>
                      </div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={alarmSettings.onu_offline}
                        onChange={(e) => setAlarmSettings({...alarmSettings, onu_offline: e.target.checked})}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                    </label>
                  </div>
                  <div className={`text-xs p-3 rounded-lg ${darkMode ? 'bg-slate-700/50 text-slate-300' : 'bg-gray-50 text-gray-600'}`}>
                    <p className="font-medium mb-1">Message includes:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li>ONU Description</li>
                      <li>Customer Address</li>
                      <li>Last Signal & Distance Before Disconnect</li>
                      <li>Region & OLT Info</li>
                    </ul>
                  </div>
                </div>

                {/* Section 3: ONU Back Online */}
                <div className={`rounded-xl border p-5 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'}`}>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${darkMode ? 'bg-blue-900/30' : 'bg-blue-100'}`}>
                        <svg className={`w-6 h-6 ${darkMode ? 'text-blue-400' : 'text-blue-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                      <div>
                        <h3 className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>ONU Back Online</h3>
                        <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Alert when ONU reconnects</p>
                      </div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={alarmSettings.onu_back_online}
                        onChange={(e) => setAlarmSettings({...alarmSettings, onu_back_online: e.target.checked})}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                    </label>
                  </div>
                  <div className={`text-xs p-3 rounded-lg ${darkMode ? 'bg-slate-700/50 text-slate-300' : 'bg-gray-50 text-gray-600'}`}>
                    <p className="font-medium mb-1">Message includes:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li>ONU Name</li>
                      <li>Downtime Duration</li>
                      <li>Current Signal Strength</li>
                      <li>Customer Address</li>
                    </ul>
                  </div>
                </div>

                {/* Section 4: OLT Offline */}
                <div className={`rounded-xl border p-5 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'}`}>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${darkMode ? 'bg-orange-900/30' : 'bg-orange-100'}`}>
                        <svg className={`w-6 h-6 ${darkMode ? 'text-orange-400' : 'text-orange-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                      </div>
                      <div>
                        <h3 className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>OLT Offline (Critical)</h3>
                        <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Alert when entire OLT goes down</p>
                      </div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={alarmSettings.olt_offline}
                        onChange={(e) => setAlarmSettings({...alarmSettings, olt_offline: e.target.checked})}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                    </label>
                  </div>
                  <div className={`text-xs p-3 rounded-lg ${darkMode ? 'bg-slate-700/50 text-slate-300' : 'bg-gray-50 text-gray-600'}`}>
                    <p className="font-medium mb-1">Message includes:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li>OLT Name & IP Address</li>
                      <li>Number of Affected ONUs</li>
                      <li>Last Seen Time</li>
                      <li>Location (if set)</li>
                    </ul>
                  </div>
                </div>

                {/* Section 5: OLT Back Online */}
                <div className={`rounded-xl border p-5 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'}`}>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${darkMode ? 'bg-teal-900/30' : 'bg-teal-100'}`}>
                        <svg className={`w-6 h-6 ${darkMode ? 'text-teal-400' : 'text-teal-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <div>
                        <h3 className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>OLT Back Online</h3>
                        <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Alert when OLT recovers</p>
                      </div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={alarmSettings.olt_back_online}
                        onChange={(e) => setAlarmSettings({...alarmSettings, olt_back_online: e.target.checked})}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                    </label>
                  </div>
                  <div className={`text-xs p-3 rounded-lg ${darkMode ? 'bg-slate-700/50 text-slate-300' : 'bg-gray-50 text-gray-600'}`}>
                    <p className="font-medium mb-1">Message includes:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li>OLT Name & IP</li>
                      <li>Downtime Duration</li>
                      <li>ONUs Restored Count</li>
                    </ul>
                  </div>
                </div>

                {/* Section 6: Weak Signal Alert */}
                <div className={`rounded-xl border p-5 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'}`}>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${darkMode ? 'bg-purple-900/30' : 'bg-purple-100'}`}>
                        <svg className={`w-6 h-6 ${darkMode ? 'text-purple-400' : 'text-purple-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <div>
                        <h3 className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>Weak Signal Alert</h3>
                        <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Alert when signal drops below threshold</p>
                      </div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={alarmSettings.weak_signal}
                        onChange={(e) => setAlarmSettings({...alarmSettings, weak_signal: e.target.checked})}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                    </label>
                  </div>
                  {alarmSettings.weak_signal && (
                    <div className="space-y-3 mb-3">
                      <div className={`p-3 rounded-lg ${darkMode ? 'bg-yellow-900/20 border border-yellow-700/30' : 'bg-yellow-50 border border-yellow-200'}`}>
                        <p className={`text-xs font-medium ${darkMode ? 'text-yellow-400' : 'text-yellow-700'}`}>
                          DANGER ZONE: Alerts when signal is between these thresholds (weak but still connected)
                        </p>
                      </div>
                      <div>
                        <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>
                          Upper Threshold (Danger Zone Start)
                        </label>
                        <input
                          type="number"
                          value={alarmSettings.weak_signal_threshold}
                          onChange={(e) => setAlarmSettings({...alarmSettings, weak_signal_threshold: parseFloat(e.target.value)})}
                          className={`w-full px-3 py-2 rounded-lg border ${darkMode ? 'bg-slate-700 border-slate-600 text-white' : 'bg-white border-gray-300'}`}
                          min="-35"
                          max="-15"
                          step="0.5"
                        />
                        <p className={`text-xs mt-1 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                          Signal weaker than this triggers warning (e.g., -25 dBm)
                        </p>
                      </div>
                      <div>
                        <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>
                          Lower Threshold (Disconnect Level)
                        </label>
                        <input
                          type="number"
                          value={alarmSettings.weak_signal_lower_threshold || -30}
                          onChange={(e) => setAlarmSettings({...alarmSettings, weak_signal_lower_threshold: parseFloat(e.target.value)})}
                          className={`w-full px-3 py-2 rounded-lg border ${darkMode ? 'bg-slate-700 border-slate-600 text-white' : 'bg-white border-gray-300'}`}
                          min="-40"
                          max="-20"
                          step="0.5"
                        />
                        <p className={`text-xs mt-1 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                          ONU typically disconnects below this (e.g., -30 dBm)
                        </p>
                      </div>
                    </div>
                  )}
                  <div className={`text-xs p-3 rounded-lg ${darkMode ? 'bg-slate-700/50 text-slate-300' : 'bg-gray-50 text-gray-600'}`}>
                    <p className="font-medium mb-1">Proactive Alert - Message includes:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li>ONU Description & Address</li>
                      <li>Current Signal & Danger Zone Range</li>
                      <li>Risk Level (CRITICAL/HIGH/WARNING)</li>
                      <li>1-hour cooldown to prevent spam</li>
                    </ul>
                  </div>
                </div>

                {/* Section 7: High Temperature Alert */}
                <div className={`rounded-xl border p-5 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'}`}>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${darkMode ? 'bg-red-900/30' : 'bg-red-100'}`}>
                        <svg className={`w-6 h-6 ${darkMode ? 'text-red-400' : 'text-red-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
                        </svg>
                      </div>
                      <div>
                        <h3 className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>High Temperature Alert</h3>
                        <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Alert when OLT temperature is high</p>
                      </div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={alarmSettings.high_temperature}
                        onChange={(e) => setAlarmSettings({...alarmSettings, high_temperature: e.target.checked})}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                    </label>
                  </div>
                  {alarmSettings.high_temperature && (
                    <div className="mb-3">
                      <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>
                        Temperature Threshold (°C)
                      </label>
                      <input
                        type="number"
                        value={alarmSettings.high_temperature_threshold}
                        onChange={(e) => setAlarmSettings({...alarmSettings, high_temperature_threshold: parseInt(e.target.value)})}
                        className={`w-full px-3 py-2 rounded-lg border ${darkMode ? 'bg-slate-700 border-slate-600 text-white' : 'bg-white border-gray-300'}`}
                        min="40"
                        max="80"
                      />
                      <p className={`text-xs mt-1 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                        Recommended: 55-65°C for most OLTs
                      </p>
                    </div>
                  )}
                  <div className={`text-xs p-3 rounded-lg ${darkMode ? 'bg-slate-700/50 text-slate-300' : 'bg-gray-50 text-gray-600'}`}>
                    <p className="font-medium mb-1">Message includes:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li>OLT Name & IP</li>
                      <li>Current Temperature</li>
                      <li>Threshold Value</li>
                    </ul>
                  </div>
                </div>

                {/* Section 8: Quiet Hours */}
                <div className={`rounded-xl border p-5 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'}`}>
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${darkMode ? 'bg-indigo-900/30' : 'bg-indigo-100'}`}>
                        <svg className={`w-6 h-6 ${darkMode ? 'text-indigo-400' : 'text-indigo-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                        </svg>
                      </div>
                      <div>
                        <h3 className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>Quiet Hours</h3>
                        <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Pause non-critical alerts at night</p>
                      </div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={alarmSettings.quiet_hours_enabled}
                        onChange={(e) => setAlarmSettings({...alarmSettings, quiet_hours_enabled: e.target.checked})}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                    </label>
                  </div>
                  {alarmSettings.quiet_hours_enabled && (
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div>
                        <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>Start</label>
                        <input
                          type="time"
                          value={alarmSettings.quiet_hours_start}
                          onChange={(e) => setAlarmSettings({...alarmSettings, quiet_hours_start: e.target.value})}
                          className={`w-full px-3 py-2 rounded-lg border ${darkMode ? 'bg-slate-700 border-slate-600 text-white' : 'bg-white border-gray-300'}`}
                        />
                      </div>
                      <div>
                        <label className={`block text-sm font-medium mb-1 ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>End</label>
                        <input
                          type="time"
                          value={alarmSettings.quiet_hours_end}
                          onChange={(e) => setAlarmSettings({...alarmSettings, quiet_hours_end: e.target.value})}
                          className={`w-full px-3 py-2 rounded-lg border ${darkMode ? 'bg-slate-700 border-slate-600 text-white' : 'bg-white border-gray-300'}`}
                        />
                      </div>
                    </div>
                  )}
                  <div className={`text-xs p-3 rounded-lg ${darkMode ? 'bg-slate-700/50 text-slate-300' : 'bg-gray-50 text-gray-600'}`}>
                    <p>During quiet hours, only <strong>OLT Offline</strong> alerts will be sent. Other alerts will be queued until morning.</p>
                  </div>
                </div>
              </div>

              {/* Select Specific ONUs Section */}
              <div className={`rounded-xl border p-5 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'}`}>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${darkMode ? 'bg-cyan-900/30' : 'bg-cyan-100'}`}>
                      <svg className={`w-6 h-6 ${darkMode ? 'text-cyan-400' : 'text-cyan-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                      </svg>
                    </div>
                    <div>
                      <h3 className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>Select Specific ONUs for Alerts</h3>
                      <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Choose which ONUs should trigger WhatsApp alerts (leave empty for all ONUs)</p>
                    </div>
                  </div>
                  {/* Show Selected Only Toggle */}
                  {alarmSettings.selected_onus.length > 0 && (
                    <label className="flex items-center gap-2 cursor-pointer">
                      <span className={`text-sm ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>Show Selected Only</span>
                      <input
                        type="checkbox"
                        checked={alarmSettings.showSelectedOnly || false}
                        onChange={(e) => setAlarmSettings({...alarmSettings, showSelectedOnly: e.target.checked})}
                        className="w-4 h-4 rounded border-gray-300 text-cyan-600 focus:ring-cyan-500"
                      />
                    </label>
                  )}
                </div>
                <div className={`max-h-60 overflow-y-auto rounded-lg border ${darkMode ? 'border-slate-600' : 'border-gray-200'}`}>
                  {onus.length === 0 ? (
                    <p className={`p-4 text-center ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>No ONUs available</p>
                  ) : (
                    <table className="w-full">
                      <thead className={`sticky top-0 ${darkMode ? 'bg-slate-700' : 'bg-gray-50'}`}>
                        <tr>
                          <th className={`px-3 py-2 text-left text-xs font-medium ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>
                            <input
                              type="checkbox"
                              checked={alarmSettings.selected_onus.length === onus.length && onus.length > 0}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setAlarmSettings({...alarmSettings, selected_onus: onus.map(o => o.id)});
                                } else {
                                  setAlarmSettings({...alarmSettings, selected_onus: []});
                                }
                              }}
                              className="rounded"
                            />
                          </th>
                          <th className={`px-3 py-2 text-left text-xs font-medium ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>Status</th>
                          <th className={`px-3 py-2 text-left text-xs font-medium ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>ONU</th>
                          <th className={`px-3 py-2 text-left text-xs font-medium ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>Description</th>
                          <th className={`px-3 py-2 text-left text-xs font-medium ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>OLT</th>
                        </tr>
                      </thead>
                      <tbody className={`divide-y ${darkMode ? 'divide-slate-700' : 'divide-gray-200'}`}>
                        {(alarmSettings.showSelectedOnly
                          ? onus.filter(onu => alarmSettings.selected_onus.includes(onu.id))
                          : onus
                        ).slice(0, 100).map((onu) => (
                          <tr key={onu.id} className={`${alarmSettings.selected_onus.includes(onu.id) ? (darkMode ? 'bg-cyan-900/20' : 'bg-cyan-50') : ''} ${darkMode ? 'hover:bg-slate-700/50' : 'hover:bg-gray-50'}`}>
                            <td className="px-3 py-2">
                              <input
                                type="checkbox"
                                checked={alarmSettings.selected_onus.includes(onu.id)}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setAlarmSettings({...alarmSettings, selected_onus: [...alarmSettings.selected_onus, onu.id]});
                                  } else {
                                    setAlarmSettings({...alarmSettings, selected_onus: alarmSettings.selected_onus.filter(id => id !== onu.id)});
                                  }
                                }}
                                className="rounded"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-2">
                                <span className={`w-2.5 h-2.5 rounded-full ${onu.is_online ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                <span className={`text-xs font-medium ${onu.is_online ? (darkMode ? 'text-green-400' : 'text-green-600') : (darkMode ? 'text-red-400' : 'text-red-600')}`}>
                                  {onu.is_online ? 'Online' : 'Offline'}
                                </span>
                              </div>
                            </td>
                            <td className={`px-3 py-2 text-sm font-medium ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>
                              {onu.pon_port}:{onu.onu_id}
                            </td>
                            <td className={`px-3 py-2 text-sm ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>
                              {onu.description || '-'}
                            </td>
                            <td className={`px-3 py-2 text-xs ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>
                              {onu.olt_name || '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
                {alarmSettings.selected_onus.length > 0 && (
                  <div className={`mt-3 flex items-center justify-between`}>
                    <p className={`text-sm font-medium ${darkMode ? 'text-cyan-400' : 'text-cyan-600'}`}>
                      {alarmSettings.selected_onus.length} ONU(s) selected for alerts
                    </p>
                    <button
                      onClick={() => setAlarmSettings({...alarmSettings, selected_onus: [], showSelectedOnly: false})}
                      className={`text-xs px-2 py-1 rounded ${darkMode ? 'bg-red-900/30 text-red-400 hover:bg-red-900/50' : 'bg-red-100 text-red-600 hover:bg-red-200'}`}
                    >
                      Clear All
                    </button>
                  </div>
                )}
              </div>

              {/* Select Regions Section */}
              <div className={`rounded-xl border p-5 ${darkMode ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'}`}>
                <div className="flex items-center gap-3 mb-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${darkMode ? 'bg-amber-900/30' : 'bg-amber-100'}`}>
                    <svg className={`w-6 h-6 ${darkMode ? 'text-amber-400' : 'text-amber-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className={`font-semibold ${darkMode ? 'text-white' : 'text-gray-800'}`}>Select Regions for Alerts</h3>
                    <p className={`text-sm ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>Enable alerts only for specific regions (leave empty for all regions)</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {regions.map((region) => (
                    <label
                      key={region.id}
                      className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-all ${
                        alarmSettings.selected_regions.includes(region.id)
                          ? (darkMode ? 'bg-blue-900/30 border-blue-600' : 'bg-blue-50 border-blue-300')
                          : (darkMode ? 'bg-slate-700/50 border-slate-600 hover:border-slate-500' : 'bg-gray-50 border-gray-200 hover:border-gray-300')
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={alarmSettings.selected_regions.includes(region.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setAlarmSettings({...alarmSettings, selected_regions: [...alarmSettings.selected_regions, region.id]});
                          } else {
                            setAlarmSettings({...alarmSettings, selected_regions: alarmSettings.selected_regions.filter(id => id !== region.id)});
                          }
                        }}
                        className="rounded"
                      />
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: region.color || '#3B82F6' }}
                      />
                      <span className={`text-sm ${darkMode ? 'text-slate-300' : 'text-gray-700'}`}>{region.name}</span>
                    </label>
                  ))}
                </div>
                {regions.length === 0 && (
                  <p className={`text-center py-4 ${darkMode ? 'text-slate-400' : 'text-gray-500'}`}>No regions configured</p>
                )}
              </div>
            </div>
          )}

          {/* Splitter Simulator Page */}
          {currentPage === 'splitter' && (
            <SplitterSimulator olts={olts} onus={onus} />
          )}

          {/* Users Page (Admin only) */}
          {currentPage === 'users' && isAdmin && (
            <>
              <div className="flex justify-between items-center mb-4">
                <h2 className={`text-lg font-bold ${darkMode ? 'text-white' : 'text-gray-800'}`}>Users</h2>
                <button
                  onClick={() => { setEditingUser(null); setShowUserModal(true); }}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
                >
                  + Add User
                </button>
              </div>
              <div className={`rounded-xl shadow-md overflow-hidden ${darkMode ? 'bg-slate-800' : 'bg-white'}`}>
                <table className={`min-w-full divide-y ${darkMode ? 'divide-slate-700' : 'divide-gray-200'}`}>
                  <thead className={darkMode ? 'bg-slate-700' : 'bg-gray-50'}>
                    <tr>
                      <th className={`px-6 py-3 text-left text-xs font-semibold uppercase ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>Username</th>
                      <th className={`px-6 py-3 text-left text-xs font-semibold uppercase ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>Full Name</th>
                      <th className={`px-6 py-3 text-left text-xs font-semibold uppercase ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>Role</th>
                      <th className={`px-6 py-3 text-left text-xs font-semibold uppercase ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>Status</th>
                      <th className={`px-6 py-3 text-left text-xs font-semibold uppercase ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>Actions</th>
                    </tr>
                  </thead>
                  <tbody className={`divide-y ${darkMode ? 'bg-slate-800 divide-slate-700' : 'bg-white divide-gray-200'}`}>
                    {users.map((u) => (
                      <tr key={u.id} className={darkMode ? 'hover:bg-slate-700/50' : 'hover:bg-gray-50'}>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm font-medium ${darkMode ? 'text-white' : 'text-gray-900'}`}>{u.username}</td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm ${darkMode ? 'text-slate-300' : 'text-gray-600'}`}>{u.full_name || '-'}</td>
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
      <EditOLTModal
        isOpen={showEditOLTModal}
        onClose={() => { setShowEditOLTModal(false); setEditingOLT(null); }}
        olt={editingOLT}
        onSubmit={handleUpdateOLT}
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
        licenseInfo={licenseInfo}
        defaultTab={settingsDefaultTab}
      />
      <TrafficGraphModal
        isOpen={showTrafficGraphModal}
        onClose={() => setShowTrafficGraphModal(false)}
        entityType={graphEntity.type}
        entityId={graphEntity.id}
        entityName={graphEntity.name}
      />
    </div>
    </DarkModeContext.Provider>
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
