%% IEEE 33-bus project: illustrative component-level averaged models
% These are transparent, simplified time-series models for initial study.
% They are NOT detailed switching converter models or a full feeder model.
% Replace illustrative values with supervisor-approved parameters.

clear; clc; close all;

%% Time axis: 24 hours
dt_h = 0.25;                         % 15-minute time step
t = 0:dt_h:24;
N = numel(t);

%% 1) Solar PV model (simple irradiance-temperature approximation)
P_pv_rated_kW = 500;                 % illustrative rated PV power
G_stc = 1000;                        % W/m^2
T_stc = 25;                          % deg C
temp_coeff = -0.004;                 % per deg C, illustrative
irradiance = max(0, 1000*sin(pi*(t-6)/12)); % simple daylight profile
cell_temp = 25 + 15*(irradiance/1000);      % illustrative cell temperature

pv_pu = (irradiance/G_stc) .* (1 + temp_coeff*(cell_temp-T_stc));
pv_pu = max(0, min(1, pv_pu));
P_pv_kW = P_pv_rated_kW .* pv_pu;

%% 2) EV charging demand profile
% Aggregate station demand; illustrative profile and 300 kW maximum.
EVCS_rated_kW = 300;
ev_profile_pu = 0.15 + 0.75*exp(-((t-19)/3.0).^2);
ev_profile_pu(t < 6) = 0.10;
ev_profile_pu = min(1, ev_profile_pu);
P_ev_kW = EVCS_rated_kW .* ev_profile_pu;

% Simple constant power-factor assumption to estimate reactive demand.
EV_power_factor = 0.98;
Q_ev_kVAr = P_ev_kW .* tan(acos(EV_power_factor));

%% 3) BESS energy/SOC model
BESS_energy_kWh = 500;               % illustrative nominal energy
BESS_power_limit_kW = 200;           % illustrative power limit
SOC_initial = 0.60;
SOC_min = 0.20;
SOC_max = 0.90;
eta_charge = 0.95;
eta_discharge = 0.95;

% Positive P_bess means discharge to support the grid.
% A simple dispatch rule discharges during evening peak and charges at midday.
P_bess_kW = zeros(1,N);
P_bess_kW((t >= 17) & (t <= 21)) = 150;
P_bess_kW((t >= 11) & (t < 14)) = -100;

SOC = zeros(1,N);
SOC(1) = SOC_initial;
for k = 2:N
    p = P_bess_kW(k-1);
    if p >= 0
        delta_soc = (p/eta_discharge) * dt_h / BESS_energy_kWh;
    else
        delta_soc = (p*eta_charge) * dt_h / BESS_energy_kWh;
    end
    SOC(k) = SOC(k-1) - delta_soc;
    SOC(k) = min(SOC_max, max(SOC_min, SOC(k)));
    % Stop dispatch if the SOC limit is reached.
    if SOC(k) <= SOC_min && P_bess_kW(k) > 0
        P_bess_kW(k) = 0;
    elseif SOC(k) >= SOC_max && P_bess_kW(k) < 0
        P_bess_kW(k) = 0;
    end
end

%% 4) Simplified DSTATCOM reactive-power support
% This is a commanded Q profile with a simple first-order response.
% It does not represent converter switching, PLL, DC-link or current limits.
Q_dstatcom_ref_kVAr = zeros(1,N);
Q_dstatcom_ref_kVAr((t >= 17) & (t <= 21)) = 150;  % inject 150 kVAr
Q_dstatcom_limit_kVAr = 200;
Q_dstatcom_ref_kVAr = max(-Q_dstatcom_limit_kVAr, ...
                         min(Q_dstatcom_limit_kVAr, Q_dstatcom_ref_kVAr));

tau_s = 0.20;                        % illustrative response time constant
dt_s = dt_h*3600;
Q_dstatcom_kVAr = zeros(1,N);
for k = 2:N
    alpha = dt_s/(tau_s + dt_s);
    Q_dstatcom_kVAr(k) = Q_dstatcom_kVAr(k-1) + ...
        alpha*(Q_dstatcom_ref_kVAr(k)-Q_dstatcom_kVAr(k-1));
end

%% 5) Plot results
figure('Name','PV output');
plot(t, P_pv_kW, 'LineWidth', 1.5); grid on;
xlabel('Time (hours)'); ylabel('PV active power (kW)');
title('Illustrative solar PV output');

figure('Name','EV demand');
plot(t, P_ev_kW, 'LineWidth', 1.5); hold on;
plot(t, Q_ev_kVAr, '--', 'LineWidth', 1.5); grid on;
xlabel('Time (hours)'); ylabel('Power (kW / kVAr)');
legend('EV active demand','EV reactive demand','Location','best');
title('Illustrative EV charging station demand');

figure('Name','BESS SOC');
yyaxis left;
plot(t, 100*SOC, 'LineWidth', 1.5);
ylabel('SOC (%)');
yyaxis right;
stairs(t, P_bess_kW, '--', 'LineWidth', 1.3);
ylabel('BESS power (kW; + discharge, - charge)');
xlabel('Time (hours)'); grid on;
title('Illustrative BESS SOC and dispatch');

figure('Name','DSTATCOM Q');
plot(t, Q_dstatcom_ref_kVAr, '--', 'LineWidth', 1.3); hold on;
plot(t, Q_dstatcom_kVAr, 'LineWidth', 1.5); grid on;
xlabel('Time (hours)'); ylabel('Reactive power (kVAr)');
legend('Q reference','Q response','Location','best');
title('Simplified DSTATCOM reactive-power response');

%% 6) Export MATLAB time-series for report / cross-platform comparison
T = table(t(:), irradiance(:), P_pv_kW(:), P_ev_kW(:), Q_ev_kVAr(:), ...
          P_bess_kW(:), SOC(:), Q_dstatcom_kVAr(:), ...
          'VariableNames', {'time_h','irradiance_Wm2','PV_kW', ...
          'EV_P_kW','EV_Q_kVAr','BESS_P_kW','BESS_SOC_pu','DSTATCOM_Q_kVAr'});
writetable(T, 'matlab_component_profiles.csv');
disp('Finished. Saved matlab_component_profiles.csv and four figures.');
