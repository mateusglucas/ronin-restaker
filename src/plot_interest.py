from matplotlib import pyplot as plt
from strategy import OptimalIntervalStrategy

# compare OptimalIntervalStrategy vs not restaking

if __name__ == "__main__":
    M0=14           # montante inicial, em USD
    c=0.01          # custo para restaking, em USD
    k=0.56/365      # taxa de crescimento linear dos tokens no staking, em 1/dia

    times=[0]
    M=[M0]

    dt_min = 1 # período mínimo entre restakings
    while times[-1]<5*365:
        dt=max(dt_min, OptimalIntervalStrategy._estimate_optimal_restake_interval(c/M[-1], k))

        times.append(times[-1]+dt)
        M.append(M[-1]*(1+k*dt)-c)
        
    plt.plot(times, [m/M0 for m in M])
    plt.plot([0, times[-1]],[1, (1+k*times[-1])])

    plt.legend(['Compound','Linear'])
    plt.grid()
    plt.xlabel('Days')
    plt.ylabel('Normalized balance')

    plt.show()