# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/106b_models.XceptionTimePlus.ipynb.

# %% auto 0
__all__ = ['XceptionModulePlus', 'XceptionBlockPlus', 'XceptionTimePlus']

# %% ../../nbs/106b_models.XceptionTimePlus.ipynb 2
from ..imports import *
from .layers import *
from .utils import *

# %% ../../nbs/106b_models.XceptionTimePlus.ipynb 3
# This is an unofficial PyTorch implementation developed by Ignacio Oguiza - timeseriesAI@gmail.com modified on:
# Rahimian, E., Zabihi, S., Atashzar, S. F., Asif, A., & Mohammadi, A. (2019). 
# XceptionTime: A Novel Deep Architecture based on Depthwise Separable Convolutions for Hand Gesture Classification. arXiv preprint arXiv:1911.03803.
# and 
# Fawaz, H. I., Lucas, B., Forestier, G., Pelletier, C., Schmidt, D. F., Weber, J., ... & Petitjean, F. (2019). 
# InceptionTime: Finding AlexNet for Time Series Classification. arXiv preprint arXiv:1909.04939.
# Official InceptionTime tensorflow implementation: https://github.com/hfawaz/InceptionTime

# added bn and relu (not in XceptionTimeModule)


    
class XceptionModulePlus(Module):
    def __init__(self, ni, nf, ks=40, kss=None, bottleneck=True, coord=False, separable=True, norm='Batch', zero_norm=False, bn_1st=True, 
                 act=nn.ReLU, act_kwargs={}, norm_act=False):
        if kss is None: kss = [ks // (2**i) for i in range(3)]
        kss = [ksi if ksi % 2 != 0 else ksi - 1 for ksi in kss]  # ensure odd kss for padding='same'
        self.bottleneck = Conv(ni, nf, 1, coord=coord, bias=False) if bottleneck else noop
        self.convs = nn.ModuleList()
        for i in range(len(kss)): self.convs.append(Conv(nf if bottleneck else ni, nf, kss[i], coord=coord, separable=separable, bias=False))
        self.mp_conv = nn.Sequential(*[nn.MaxPool1d(3, stride=1, padding=1), Conv(ni, nf, 1, coord=coord, bias=False)])
        self.concat = Concat()
        _norm_act = []
        if act is not None: _norm_act.append(act(**act_kwargs))
        _norm_act.append(Norm(nf * 4, norm=norm, zero_norm=zero_norm))
        if bn_1st: _norm_act.reverse()
        self.norm_act = noop if not norm_act else _norm_act[0] if act is None else nn.Sequential(*_norm_act)

    def forward(self, x):
        input_tensor = x
        x = self.bottleneck(x)
        x = self.concat([l(x) for l in self.convs] + [self.mp_conv(input_tensor)])
        return self.norm_act(x) 
    

@delegates(XceptionModulePlus.__init__)
class XceptionBlockPlus(Module):
    def __init__(self, ni, nf, residual=True, coord=False, norm='Batch', zero_norm=False, act=nn.ReLU, act_kwargs={}, **kwargs):
        self.residual = residual
        self.xception, self.shortcut, self.act = nn.ModuleList(), nn.ModuleList(), nn.ModuleList()
        for i in range(4):
            if self.residual and (i-1) % 2 == 0: 
                self.shortcut.append(Norm(n_in, norm=norm) if n_in == n_out else 
                                     ConvBlock(n_in, n_out * 4 * 2, 1, coord=coord, bias=False, norm=norm, act=None))
                self.act.append(act(**act_kwargs))
            n_out = nf * 2 ** i
            n_in = ni if i == 0 else n_out * 2
            self.xception.append(XceptionModulePlus(n_in, n_out, coord=coord, 
                                                    norm=norm, zero_norm=zero_norm if self.residual and (i-1) % 2 == 0 else False, 
                                                    act=act if self.residual and (i-1) % 2 == 0 else None, **kwargs))
        self.add = Add()
        
    def forward(self, x):
        res = x
        for i in range(4):
            x = self.xception[i](x)
            if self.residual and (i + 1) % 2 == 0: res = x = self.act[i//2](self.add(x, self.shortcut[i//2](res)))
        return x
    
    
@delegates(XceptionBlockPlus.__init__)
class XceptionTimePlus(nn.Sequential):
    def __init__(self, c_in, c_out, nf=16, nb_filters=None, coord=False, norm='Batch', concat_pool=False, adaptive_size=50, **kwargs):            
        nf = ifnone(nf, nb_filters)
        # Backbone
        backbone = XceptionBlockPlus(c_in, nf, coord=coord, norm=norm, **kwargs)
        
        # Head
        gap1 = AdaptiveConcatPool1d(adaptive_size) if adaptive_size and concat_pool else nn.AdaptiveAvgPool1d(adaptive_size) if adaptive_size else noop
        mult = 2 if adaptive_size and concat_pool else 1
        conv1x1_1 = ConvBlock(nf * 32 * mult, nf * 16 * mult, 1, coord=coord, norm=norm)
        conv1x1_2 = ConvBlock(nf * 16 * mult, nf * 8 * mult, 1, coord=coord, norm=norm)
        conv1x1_3 = ConvBlock(nf * 8 * mult, c_out, 1, coord=coord, norm=norm)
        gap2 = GAP1d(1)
        head = nn.Sequential(gap1, conv1x1_1, conv1x1_2, conv1x1_3, gap2)
        
        super().__init__(OrderedDict([('backbone', backbone), ('head', head)]))
