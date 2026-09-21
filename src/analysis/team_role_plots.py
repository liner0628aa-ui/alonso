"""Static plots of computed Milestone 2 tables; no model calculations here."""
import numpy as np
from src.analysis.team_role_space import ROLE_FEATURES, WIRTZ


def plot_outputs(result, neighbours, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'figure.facecolor':'#f8fafc','axes.facecolor':'#f8fafc','font.size':10})
    seasons=result['seasons'];pca=result['pca'];selected=result['selected']
    colors=plt.get_cmap('tab20')(np.linspace(0,1,len(seasons)))
    color_by_id={r['player_id']:colors[i] for i,r in enumerate(seasons)}
    labels=[r['player_name'] for r in seasons]
    short_labels=[r['player_name'] for r in seasons]
    def save(fig,name):
        fig.text(.015,.012,'Data: StatsBomb Open Data | Bundesliga 2023/24 | Observed behaviour; not ability or coaching instructions',fontsize=8,color='#475569')
        fig.tight_layout(rect=(0,.035,1,.98));fig.savefig(out/name,dpi=170);plt.close(fig)
    def pca_axes(ax,title):
        ax.set(xlabel=f'PC1 ({pca.explained_variance_ratio_[0]:.1%})',ylabel=f'PC2 ({pca.explained_variance_ratio_[1]:.1%})',title=title)
        ax.axhline(0,color='#cbd5e1',lw=.7);ax.axvline(0,color='#cbd5e1',lw=.7);ax.grid(alpha=.15)
    def legend_panel(ax):
        ax.axis('off')
        ax.set_title('Player / eligible matches',loc='left')
        for i,r in enumerate(seasons):
            y=.96-i*.94/max(len(seasons),1)
            ax.text(0,y,f"{i+1:02d}  {r['player_name']}  (n={r['match_count']})",color=color_by_id[r['player_id']],
                    fontsize=9,weight='bold' if r['player_id']==WIRTZ else 'normal',transform=ax.transAxes)
    for show_matches,name in [(False,'pca_player_role_map.png'),(True,'pca_player_match_map.png')]:
        fig,(ax,key)=plt.subplots(1,2,figsize=(14,8),gridspec_kw={'width_ratios':[2.1,1]})
        pca_axes(ax,'Player-match points + minute-weighted centroids' if show_matches else 'Player-season minute-weighted centroids')
        if show_matches:
            for r in selected:ax.scatter(r['PC1'],r['PC2'],s=12,alpha=.25,color=color_by_id[r['player_id']],edgecolors='none')
        for i,r in enumerate(seasons):
            ax.scatter(r['PC1'],r['PC2'],s=160 if r['player_id']==WIRTZ else 100,color=color_by_id[r['player_id']],edgecolor='#334155',lw=.7,zorder=4)
            ax.annotate(str(i+1),(r['PC1'],r['PC2']),xytext=(5,7 if i%2 else -12),textcoords='offset points',fontsize=9,weight='bold')
        legend_panel(key);save(fig,name)
    fig,ax=plt.subplots(figsize=(12,10))
    sim=np.array([[np.nan if v is None else v for v in row] for row in result['similarity']])
    im=ax.imshow(sim,vmin=-1,vmax=1,cmap='RdBu_r')
    ax.set_xticks(range(len(labels)),labels,rotation=70,ha='right',fontsize=8)
    ax.set_yticks(range(len(labels)),labels,fontsize=8)
    ax.set_title('Full standardized feature-space cosine similarity\nObserved behaviour relative to the team-match mean')
    fig.colorbar(im,ax=ax,label='Raw cosine (−1 to +1)',shrink=.75)
    save(fig,'player_similarity_heatmap.png')
    fig,ax=plt.subplots(figsize=(10,5))
    ax.barh([r['player_name'] for r in neighbours],[r['cosine_similarity'] for r in neighbours],color='#2563eb')
    for i,r in enumerate(neighbours):ax.text(r['cosine_similarity']+.015,i,f"{r['cosine_similarity']:.3f}",va='center')
    ax.set(xlim=(-1,1.12),xlabel='Raw cosine similarity (all selected dimensions)',title='Wirtz | Five nearest observed roles');ax.invert_yaxis();ax.axvline(0,color='#64748b',lw=.7)
    save(fig,'wirtz_nearest_roles.png')
    ordered=sorted(result['stability'],key=lambda r:r['cosine_mean'] if r['cosine_mean'] is not None else -2,reverse=True)
    fig,(ax,dist)=plt.subplots(1,2,figsize=(15,9),gridspec_kw={'width_ratios':[2,1]})
    values=[[r['cosine_to_centroid'] for r in result['match_stability'] if r['player_id']==s['player_id'] and r['cosine_to_centroid'] is not None] for s in ordered]
    ax.boxplot(values,orientation='horizontal',tick_labels=[f"{r['player_name']} (n={r['match_count']})" for r in ordered],showfliers=True)
    ax.invert_yaxis();ax.set(xlim=(-1,1),xlabel='Match-to-own-centroid cosine',title='Within-player angular stability\nOwn centroid includes the match')
    dist.barh(range(1,len(ordered)+1),[r['rms_standardized_distance'] for r in ordered],color='#0d9488')
    dist.set_yticks(range(1,len(ordered)+1),['']*len(ordered));dist.set_ylim(ax.get_ylim())
    dist.set(xlabel='RMS standardized Euclidean distance',title='Absolute feature variability\nSame player order');save(fig,'role_stability.png')
    fig,axes=plt.subplots(1,2,figsize=(15,8),sharey=True)
    for c,ax in enumerate(axes):
        vals=pca.components_[c]
        ax.barh(ROLE_FEATURES,vals,color=['#2563eb' if v>=0 else '#ea580c' for v in vals]);ax.axvline(0,color='#64748b',lw=.8)
        ax.set(title=f'PC{c+1} | {pca.explained_variance_ratio_[c]:.1%} explained variance',xlabel='Eigenvector coefficient (sign is arbitrary)')
    axes[0].invert_yaxis();save(fig,'feature_loadings.png')
    fig,ax=plt.subplots(figsize=(14,9))
    centers=np.array([[r[k+'_z'] for k in ROLE_FEATURES] for r in seasons])
    bound=max(1,float(np.max(np.abs(centers))))
    im=ax.imshow(centers,cmap='RdBu_r',vmin=-bound,vmax=bound,aspect='auto')
    ax.set_xticks(range(len(ROLE_FEATURES)),ROLE_FEATURES,rotation=60,ha='right',fontsize=8);ax.set_yticks(range(len(labels)),labels,fontsize=9)
    ax.set_title('Core player role profiles | minute-weighted standardized means')
    fig.colorbar(im,ax=ax,label='Standard deviations from eligible match mean');save(fig,'core_player_role_profiles.png')
