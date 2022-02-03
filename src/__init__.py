from pkg_resources import DistributionNotFound, get_distribution


try:
    __version__ = get_distribution('ipmi-fan-controller').version
except DistributionNotFound:
    __version__ = '(local)'
