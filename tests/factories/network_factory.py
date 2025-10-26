"""
NetworkDataFactory - Generate realistic synthetic network structures.

This factory generates network data structures for testing visualizations:
- Issue-website bipartite networks (queries → websites)
- Website-noun bipartite networks (websites → nouns)
- Website-concept knowledge graphs (directed)
- Power law degree distribution
- Realistic edge weights
- Community structure
- GEXF export support
"""
from typing import Dict, List, Optional, Any, Tuple
import random
import numpy as np
import networkx as nx

from .base import (
    set_seed,
    generate_power_law_distribution,
    weighted_choice,
    get_issue_vocabulary
)


class NetworkDataFactory:
    """Generate synthetic network data for different network types."""

    # Domain distribution for realistic websites
    DOMAIN_DISTRIBUTION = {
        '.com': 0.4,
        '.org': 0.2,
        '.edu': 0.1,
        '.gov': 0.1,
        '.dk': 0.1,
        '.eu': 0.1
    }

    # Concept clusters for knowledge graphs
    CONCEPT_CLUSTERS = {
        'scientific_consensus': {
            'concepts': [
                'peer-reviewed research', 'empirical evidence', 'scientific method',
                'data analysis', 'reproducibility', 'systematic review'
            ],
            'color': '#3b82f6'
        },
        'policy_debate': {
            'concepts': [
                'regulatory framework', 'government intervention', 'policy instruments',
                'legislation', 'compliance', 'governance'
            ],
            'color': '#8b5cf6'
        },
        'public_discourse': {
            'concepts': [
                'public opinion', 'media representation', 'social movements',
                'advocacy', 'awareness campaigns', 'stakeholder engagement'
            ],
            'color': '#10b981'
        },
        'economic_impacts': {
            'concepts': [
                'market dynamics', 'cost-benefit analysis', 'economic growth',
                'investment', 'financial incentives', 'return on investment'
            ],
            'color': '#f59e0b'
        },
        'technological_innovation': {
            'concepts': [
                'breakthrough technology', 'R&D', 'innovation ecosystem',
                'patents', 'technology transfer', 'scaling solutions'
            ],
            'color': '#ef4444'
        }
    }

    @classmethod
    def create_issue_website_network(
        cls,
        num_queries: int = 5,
        num_websites: int = 50,
        seed: Optional[int] = None
    ) -> nx.Graph:
        """
        Generate bipartite network of search queries to websites.

        This represents the Issue Observatory's core structure where
        queries (representing different aspects of an issue) link to
        websites found in search results.

        Args:
            num_queries: Number of query nodes
            num_websites: Number of website nodes
            seed: Random seed for reproducibility

        Returns:
            NetworkX Graph with bipartite structure

        Example:
            >>> G = NetworkDataFactory.create_issue_website_network(3, 20, seed=42)
            >>> assert G.number_of_nodes() == 23  # 3 queries + 20 websites
            >>> # Check bipartite structure
            >>> query_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'query']
            >>> assert len(query_nodes) == 3
        """
        if seed is not None:
            set_seed(seed)

        G = nx.Graph()

        # Add query nodes
        queries = []
        for i in range(num_queries):
            query_id = f"query_{i}"
            queries.append(query_id)
            G.add_node(
                query_id,
                node_type='query',
                bipartite=0,
                color='#3b82f6',
                size=30,
                label=f"Query {i+1}"
            )

        # Add website nodes with realistic domain distribution
        websites = []
        for i in range(num_websites):
            domain = weighted_choice(cls.DOMAIN_DISTRIBUTION, seed=seed)
            website_id = f"website{i}{domain}"
            websites.append(website_id)

            # Calculate node size based on expected degree (power law)
            size = 10 + random.randint(0, 20)

            G.add_node(
                website_id,
                node_type='website',
                bipartite=1,
                color='#10b981',
                size=size,
                label=website_id,
                domain=domain
            )

        # Add edges with rank-based weights
        # Each query connects to a subset of websites
        for query in queries:
            # Number of results per query (realistic: 10-30)
            num_results = random.randint(10, min(30, num_websites))

            # Select websites for this query
            connected_sites = random.sample(websites, num_results)

            for rank, site in enumerate(connected_sites, 1):
                # Weight inversely proportional to rank (higher rank = lower weight)
                weight = 1.0 / rank
                G.add_edge(
                    query,
                    site,
                    weight=weight,
                    rank=rank,
                    color='#cbd5e1'
                )

        return G

    @classmethod
    def create_website_noun_network(
        cls,
        num_websites: int = 30,
        num_nouns: int = 100,
        seed: Optional[int] = None
    ) -> nx.Graph:
        """
        Generate bipartite network of websites to extracted nouns.

        Represents NLP extraction results where websites link to
        the key nouns extracted from their content.

        Args:
            num_websites: Number of website nodes
            num_nouns: Number of noun nodes
            seed: Random seed

        Returns:
            NetworkX Graph with bipartite structure

        Example:
            >>> G = NetworkDataFactory.create_website_noun_network(10, 50, seed=42)
            >>> assert G.number_of_nodes() == 60  # 10 + 50
            >>> # Check nouns have categories
            >>> noun_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'noun']
            >>> assert all('category' in G.nodes[n] for n in noun_nodes)
        """
        if seed is not None:
            set_seed(seed)

        G = nx.Graph()

        # Add website nodes
        websites = []
        for i in range(num_websites):
            website_id = f"site_{i}.com"
            websites.append(website_id)
            G.add_node(
                website_id,
                node_type='website',
                bipartite=0,
                color='#10b981',
                size=20,
                label=website_id
            )

        # Define noun categories
        noun_categories = {
            'technical': ['algorithm', 'data', 'system', 'network', 'protocol', 'infrastructure'],
            'environmental': ['climate', 'energy', 'sustainability', 'emissions', 'renewable', 'conservation'],
            'social': ['society', 'community', 'policy', 'governance', 'equality', 'justice'],
            'economic': ['market', 'investment', 'growth', 'innovation', 'trade', 'finance']
        }

        # Generate noun nodes
        nouns = []
        category_colors = {
            'technical': '#3b82f6',
            'environmental': '#10b981',
            'social': '#8b5cf6',
            'economic': '#f59e0b'
        }

        noun_count = 0
        for category, base_terms in noun_categories.items():
            for term in base_terms:
                # Create variations
                variants = [term, f"{term}s", f"{term}_analysis", f"new_{term}"]
                for variant in variants:
                    if noun_count >= num_nouns:
                        break

                    nouns.append(variant)
                    G.add_node(
                        variant,
                        node_type='noun',
                        bipartite=1,
                        category=category,
                        color=category_colors[category],
                        size=15,
                        label=variant
                    )
                    noun_count += 1

                if noun_count >= num_nouns:
                    break

            if noun_count >= num_nouns:
                break

        # Connect websites to nouns with TF-IDF weighted edges
        for site in websites:
            # Each website connects to 5-20 nouns
            num_connections = random.randint(5, min(20, len(nouns)))
            site_nouns = random.sample(nouns, num_connections)

            for noun in site_nouns:
                # Generate realistic TF-IDF weight (following power law)
                tfidf = random.uniform(0.1, 0.9)
                G.add_edge(
                    site,
                    noun,
                    weight=tfidf,
                    color='#cbd5e1'
                )

        return G

    @classmethod
    def create_website_concept_network(
        cls,
        num_websites: int = 25,
        num_concepts: int = 15,
        seed: Optional[int] = None
    ) -> nx.DiGraph:
        """
        Generate directed knowledge graph of websites to concepts.

        Represents semantic relationships where websites discuss
        specific concepts organized into thematic clusters.

        Args:
            num_websites: Number of website nodes
            num_concepts: Number of concept nodes (distributed across clusters)
            seed: Random seed

        Returns:
            NetworkX DiGraph (directed)

        Example:
            >>> G = NetworkDataFactory.create_website_concept_network(10, 15, seed=42)
            >>> assert isinstance(G, nx.DiGraph)
            >>> # Check concepts have clusters
            >>> concept_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'concept']
            >>> assert all('cluster' in G.nodes[n] for n in concept_nodes)
        """
        if seed is not None:
            set_seed(seed)

        G = nx.DiGraph()  # Directed for knowledge flow

        # Add website nodes
        websites = []
        for i in range(num_websites):
            website_id = f"website_{i}"
            websites.append(website_id)
            G.add_node(
                website_id,
                node_type='website',
                color='#10b981',
                size=20,
                label=website_id
            )

        # Add concept nodes from clusters
        concepts = []
        concept_count = 0
        concepts_per_cluster = num_concepts // len(cls.CONCEPT_CLUSTERS)

        for cluster_name, cluster_data in cls.CONCEPT_CLUSTERS.items():
            for concept in cluster_data['concepts']:
                if concept_count >= num_concepts:
                    break

                concepts.append(concept)
                G.add_node(
                    concept,
                    node_type='concept',
                    cluster=cluster_name,
                    color=cluster_data['color'],
                    size=25,
                    label=concept
                )
                concept_count += 1

                # Connect to relevant websites
                num_connections = random.randint(3, min(10, len(websites)))
                connected_sites = random.sample(websites, num_connections)

                for site in connected_sites:
                    # Relevance score (0.5 to 1.0)
                    relevance = random.uniform(0.5, 1.0)
                    G.add_edge(
                        site,
                        concept,
                        weight=relevance,
                        color='#cbd5e1',
                        label=f"{relevance:.2f}"
                    )

            if concept_count >= num_concepts:
                break

        return G

    @classmethod
    def create_large_scale_network(
        cls,
        size: str = 'medium',
        seed: Optional[int] = None
    ) -> nx.Graph:
        """
        Generate large-scale networks for performance testing.

        Args:
            size: Network size ('small', 'medium', 'large', 'huge')
                - small: ~100 nodes, ~200 edges
                - medium: ~1000 nodes, ~2000 edges
                - large: ~5000 nodes, ~10000 edges
                - huge: ~10000 nodes, ~20000 edges
            seed: Random seed

        Returns:
            NetworkX Graph

        Example:
            >>> G = NetworkDataFactory.create_large_scale_network('medium', seed=42)
            >>> assert G.number_of_nodes() >= 1000
            >>> assert G.number_of_edges() >= 2000
        """
        if seed is not None:
            set_seed(seed)

        size_params = {
            'small': (100, 200),
            'medium': (1000, 2000),
            'large': (5000, 10000),
            'huge': (10000, 20000)
        }

        num_nodes, num_edges = size_params.get(size, size_params['medium'])

        # Use Barabási-Albert model for power law degree distribution
        # m = number of edges to attach from new node
        m = max(1, num_edges // num_nodes)

        G = nx.barabasi_albert_graph(num_nodes, m, seed=seed)

        # Add realistic attributes
        for node in G.nodes():
            node_type = 'website' if random.random() > 0.3 else 'query'
            G.nodes[node]['node_type'] = node_type
            G.nodes[node]['color'] = '#10b981' if node_type == 'website' else '#3b82f6'
            G.nodes[node]['size'] = 10 + random.randint(0, 20)

        # Add edge weights
        for u, v in G.edges():
            G.edges[u, v]['weight'] = random.uniform(0.1, 1.0)

        return G

    @classmethod
    def create_community_structured_network(
        cls,
        num_communities: int = 5,
        nodes_per_community: int = 20,
        p_intra: float = 0.3,
        p_inter: float = 0.05,
        seed: Optional[int] = None
    ) -> nx.Graph:
        """
        Generate network with clear community structure.

        Useful for testing community detection algorithms.

        Args:
            num_communities: Number of communities
            nodes_per_community: Nodes in each community
            p_intra: Probability of edge within community
            p_inter: Probability of edge between communities
            seed: Random seed

        Returns:
            NetworkX Graph with community structure

        Example:
            >>> G = NetworkDataFactory.create_community_structured_network(3, 10, seed=42)
            >>> assert G.number_of_nodes() == 30  # 3 * 10
            >>> # Check community attribute
            >>> assert all('community' in G.nodes[n] for n in G.nodes())
        """
        if seed is not None:
            set_seed(seed)

        # Generate planted partition model
        sizes = [nodes_per_community] * num_communities
        probs = [[p_intra if i == j else p_inter for j in range(num_communities)]
                 for i in range(num_communities)]

        G = nx.stochastic_block_model(sizes, probs, seed=seed)

        # Add community labels and attributes
        node_to_community = {}
        node_idx = 0
        for comm_idx in range(num_communities):
            for _ in range(nodes_per_community):
                node_to_community[node_idx] = comm_idx
                node_idx += 1

        # Community colors
        colors = ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444']

        for node in G.nodes():
            community = node_to_community[node]
            G.nodes[node]['community'] = community
            G.nodes[node]['color'] = colors[community % len(colors)]
            G.nodes[node]['size'] = 15

        # Add edge weights
        for u, v in G.edges():
            # Higher weight for intra-community edges
            if node_to_community[u] == node_to_community[v]:
                weight = random.uniform(0.6, 1.0)
            else:
                weight = random.uniform(0.1, 0.4)

            G.edges[u, v]['weight'] = weight

        return G

    @classmethod
    def export_to_gexf(
        cls,
        G: nx.Graph,
        include_viz: bool = True
    ) -> str:
        """
        Export network to GEXF format string.

        Args:
            G: NetworkX graph
            include_viz: Include visualization attributes

        Returns:
            GEXF XML string

        Example:
            >>> G = NetworkDataFactory.create_issue_website_network(3, 10)
            >>> gexf_str = NetworkDataFactory.export_to_gexf(G)
            >>> assert '<gexf' in gexf_str
            >>> assert '</gexf>' in gexf_str
        """
        import io

        # Create string buffer
        buffer = io.BytesIO()

        # Write to buffer
        nx.write_gexf(G, buffer)

        # Get string
        gexf_str = buffer.getvalue().decode('utf-8')

        return gexf_str

    @classmethod
    def calculate_network_metrics(cls, G: nx.Graph) -> Dict[str, Any]:
        """
        Calculate comprehensive network metrics.

        Args:
            G: NetworkX graph

        Returns:
            Dictionary of network metrics

        Example:
            >>> G = NetworkDataFactory.create_issue_website_network(5, 20)
            >>> metrics = NetworkDataFactory.calculate_network_metrics(G)
            >>> assert 'num_nodes' in metrics
            >>> assert 'num_edges' in metrics
            >>> assert 'density' in metrics
        """
        metrics = {
            'num_nodes': G.number_of_nodes(),
            'num_edges': G.number_of_edges(),
            'density': nx.density(G),
            'is_connected': nx.is_connected(G) if not G.is_directed() else nx.is_weakly_connected(G),
        }

        # Degree statistics
        degrees = [d for n, d in G.degree()]
        metrics['avg_degree'] = np.mean(degrees)
        metrics['max_degree'] = np.max(degrees)
        metrics['min_degree'] = np.min(degrees)

        # Connected components
        if not G.is_directed():
            metrics['num_components'] = nx.number_connected_components(G)
        else:
            metrics['num_weakly_connected'] = nx.number_weakly_connected_components(G)
            metrics['num_strongly_connected'] = nx.number_strongly_connected_components(G)

        # Clustering (for undirected)
        if not G.is_directed() and G.number_of_nodes() > 0:
            try:
                metrics['avg_clustering'] = nx.average_clustering(G)
            except:
                metrics['avg_clustering'] = 0.0

        return metrics

    @classmethod
    def create_temporal_network_snapshots(
        cls,
        num_snapshots: int = 5,
        initial_nodes: int = 20,
        growth_rate: float = 1.2,
        seed: Optional[int] = None
    ) -> List[nx.Graph]:
        """
        Generate temporal network snapshots showing growth over time.

        Useful for testing temporal analysis features.

        Args:
            num_snapshots: Number of time snapshots
            initial_nodes: Nodes in first snapshot
            growth_rate: Multiplicative growth rate per snapshot
            seed: Random seed

        Returns:
            List of NetworkX graphs (one per snapshot)

        Example:
            >>> snapshots = NetworkDataFactory.create_temporal_network_snapshots(3, 10, 1.5)
            >>> assert len(snapshots) == 3
            >>> # Network should grow over time
            >>> assert snapshots[0].number_of_nodes() < snapshots[-1].number_of_nodes()
        """
        if seed is not None:
            set_seed(seed)

        snapshots = []

        for i in range(num_snapshots):
            num_nodes = int(initial_nodes * (growth_rate ** i))
            num_edges = num_nodes * 2  # Keep avg degree ~4

            # Create network
            G = cls.create_large_scale_network('small', seed=seed + i if seed else None)

            # Resize to target
            if G.number_of_nodes() > num_nodes:
                # Remove nodes
                nodes_to_remove = list(G.nodes())[num_nodes:]
                G.remove_nodes_from(nodes_to_remove)
            elif G.number_of_nodes() < num_nodes:
                # Add nodes
                for j in range(G.number_of_nodes(), num_nodes):
                    G.add_node(j, node_type='website', color='#10b981', size=15)

            # Add timestamp attribute
            for node in G.nodes():
                G.nodes[node]['timestamp'] = i

            snapshots.append(G)

        return snapshots
