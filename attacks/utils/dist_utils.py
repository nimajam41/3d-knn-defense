# credits: https://github.com/Wuziyi616/IF-Defense/tree/main/baselines/attack/util

import numpy as np
import torch
import torch.nn as nn


class _Distance(nn.Module):

    def __init__(self):
        super(_Distance, self).__init__()
        self.use_cuda = torch.cuda.is_available()

    def forward(self, preds, gts):
        pass

    def batch_pairwise_dist(self, x, y):
        bs, num_points_x, points_dim = x.size()
        _, num_points_y, _ = y.size()
        xx = torch.bmm(x, x.transpose(2, 1))  # [B, K, K]
        yy = torch.bmm(y, y.transpose(2, 1))
        zz = torch.bmm(x, y.transpose(2, 1))
        if self.use_cuda:
            dtype = torch.cuda.LongTensor
        else:
            dtype = torch.LongTensor
        diag_ind_x = torch.arange(0, num_points_x).type(dtype)
        diag_ind_y = torch.arange(0, num_points_y).type(dtype)
        # brk()
        rx = xx[:, diag_ind_x, diag_ind_x].unsqueeze(
            1).expand_as(zz.transpose(2, 1))
        ry = yy[:, diag_ind_y, diag_ind_y].unsqueeze(1).expand_as(zz)
        P = (rx.transpose(2, 1) + ry - 2 * zz)
        return P


class ChamferDistance(_Distance):

    def __init__(self):
        super(ChamferDistance, self).__init__()

    def forward(self, preds, gts):
        """
        preds: [B, N1, 3]
        gts: [B, N2, 3]
        """
        P = self.batch_pairwise_dist(gts, preds)  # [B, N2, N1]
        mins, _ = torch.min(P, 1)  # [B, N1], find preds' nearest points in gts
        loss1 = torch.mean(mins, dim=1)  # [B]
        mins, _ = torch.min(P, 2)  # [B, N2], find gts' nearest points in preds
        loss2 = torch.mean(mins, dim=1)  # [B]
        return loss1, loss2


class HausdorffDistance(_Distance):

    def __init__(self):
        super(HausdorffDistance, self).__init__()

    def forward(self, preds, gts):
        """
        preds: [B, N1, 3]
        gts: [B, N2, 3]
        """
        P = self.batch_pairwise_dist(gts, preds)  # [B, N2, N1]
        # max_{y \in pred} min_{x \in gt}
        mins, _ = torch.min(P, 1)  # [B, N1]
        loss1 = torch.max(mins, dim=1)[0]  # [B]
        # max_{y \in gt} min_{x \in pred}
        mins, _ = torch.min(P, 2)  # [B, N2]
        loss2 = torch.max(mins, dim=1)[0]  # [B]
        return loss1, loss2


chamfer = ChamferDistance()
hausdorff = HausdorffDistance()


class L2Dist(nn.Module):

    def __init__(self):
        """Compute global L2 distance between two point clouds.
        """
        super(L2Dist, self).__init__()

    def forward(self, adv_pc, ori_pc,
                weights=None, batch_avg=True):
        """Compute L2 distance between two point clouds.
        Apply different weights for batch input for CW attack.

        Args:
            adv_pc (torch.FloatTensor): [B, K, 3] or [B, 3, K]
            ori_pc (torch.FloatTensor): [B, K, 3] or [B, 3, k]
            weights (torch.FloatTensor, optional): [B], if None, just use avg
            batch_avg: (bool, optional): whether to avg over batch dim
        """
        B = adv_pc.shape[0]

        if weights is None:
            weights = torch.ones((B,))
        weights = weights.float().cuda()

        dist = torch.sqrt(torch.sum(
            (adv_pc - ori_pc) ** 2, dim=[1, 2]))  # [B]
        dist = dist * weights

        if batch_avg:
            return dist.mean()
        
        return dist
    

class ChamferDist(nn.Module):

    def __init__(self, method='adv2ori'):
        """Compute chamfer distance between two point clouds.

        Args:
            method (str, optional): type of chamfer. Defaults to 'adv2ori'.
        """
        super(ChamferDist, self).__init__()

        self.method = method

    def forward(self, adv_pc, ori_pc,
                weights=None, batch_avg=True):
        """Compute chamfer distance between two point clouds.

        Args:
            adv_pc (torch.FloatTensor): [B, K, 3]
            ori_pc (torch.FloatTensor): [B, K, 3]
            weights (torch.FloatTensor, optional): [B], if None, just use avg
            batch_avg: (bool, optional): whether to avg over batch dim
        """
        B = adv_pc.shape[0]
        
        if weights is None:
            weights = torch.ones((B,))

        loss1, loss2 = chamfer(adv_pc, ori_pc)  # [B], adv2ori, ori2adv

        if self.method == 'adv2ori':
            loss = loss1

        elif self.method == 'ori2adv':
            loss = loss2
        
        else:
            loss = (loss1 + loss2) / 2.
        
        weights = weights.float().cuda()
        loss = loss * weights
        
        if batch_avg:
            return loss.mean()
        
        return loss


class HausdorffDist(nn.Module):

    def __init__(self, method='adv2ori'):
        """Compute hausdorff distance between two point clouds.

        Args:
            method (str, optional): type of hausdorff. Defaults to 'adv2ori'.
        """
        super(HausdorffDist, self).__init__()

        self.method = method

    def forward(self, adv_pc, ori_pc,
                weights=None, batch_avg=True):
        """Compute hausdorff distance between two point clouds.

        Args:
            adv_pc (torch.FloatTensor): [B, K, 3]
            ori_pc (torch.FloatTensor): [B, K, 3]
            weights (torch.FloatTensor, optional): [B], if None, just use avg
            batch_avg: (bool, optional): whether to avg over batch dim
        """
        B = adv_pc.shape[0]
        
        if weights is None:
            weights = torch.ones((B,))
        
        loss1, loss2 = hausdorff(adv_pc, ori_pc)  # [B], adv2ori, ori2adv
        
        if self.method == 'adv2ori':
            loss = loss1
        
        elif self.method == 'ori2adv':
            loss = loss2
        
        else:
            loss = (loss1 + loss2) / 2.
        
        weights = weights.float().cuda()
        loss = loss * weights
        
        if batch_avg:
            return loss.mean()
        
        return loss


class KNNDist(nn.Module):

    def __init__(self, k=5, alpha=1.05):
        """Compute kNN distance punishment within a point cloud.

        Args:
            k (int, optional): kNN neighbor num. Defaults to 5.
            alpha (float, optional): threshold = mean + alpha * std. Defaults to 1.05.
        """
        super(KNNDist, self).__init__()

        self.k = k
        self.alpha = alpha

    def forward(self, pc, weights=None, batch_avg=True):
        """KNN distance loss described in AAAI'20 paper.

        Args:
            adv_pc (torch.FloatTensor): [B, K, 3]
            weights (torch.FloatTensor, optional): [B]. Defaults to None.
            batch_avg: (bool, optional): whether to avg over batch dim
        """
        # build kNN graph
        B, K = pc.shape[:2]
        pc = pc.transpose(2, 1)  # [B, 3, K]
        inner = -2. * torch.matmul(pc.transpose(2, 1), pc)  # [B, K, K]
        
        xx = torch.sum(pc ** 2, dim=1, keepdim=True)  # [B, 1, K]
        dist = xx + inner + xx.transpose(2, 1)  # [B, K, K], l2^2
        assert dist.min().item() >= -1e-6
        
        # the min is self so we take top (k + 1)
        neg_value, _ = (-dist).topk(k=self.k + 1, dim=-1)
        
        # [B, K, k + 1]
        value = -(neg_value[..., 1:])  # [B, K, k]
        value = torch.mean(value, dim=-1)  # d_p, [B, K]
        
        with torch.no_grad():
            mean = torch.mean(value, dim=-1)  # [B]
            std = torch.std(value, dim=-1)  # [B]
            
            # [B], penalty threshold for batch
            threshold = mean + self.alpha * std
            weight_mask = (value > threshold[:, None]).\
                float().detach()  # [B, K]
        
        loss = torch.mean(value * weight_mask, dim=1)  # [B]
        
        # accumulate loss
        if weights is None:
            weights = torch.ones((B,))
        
        weights = weights.float().cuda()
        loss = loss * weights
        
        if batch_avg:
            return loss.mean()
        
        return loss


class ChamferkNNDist(nn.Module):

    def __init__(self, chamfer_method='adv2ori',
                 knn_k=5, knn_alpha=1.05,
                 chamfer_weight=5., knn_weight=3.):
        """Geometry-aware distance function of AAAI'20 paper.

        Args:
            chamfer_method (str, optional): chamfer. Defaults to 'adv2ori'.
            knn_k (int, optional): k in kNN. Defaults to 5.
            knn_alpha (float, optional): alpha in kNN. Defaults to 1.1.
            chamfer_weight (float, optional): weight factor. Defaults to 5..
            knn_weight (float, optional): weight factor. Defaults to 3..
        """
        super(ChamferkNNDist, self).__init__()

        self.chamfer_dist = ChamferDist(method=chamfer_method)
        self.knn_dist = KNNDist(k=knn_k, alpha=knn_alpha)
        self.w1 = chamfer_weight
        self.w2 = knn_weight

    def forward(self, adv_pc, ori_pc,
                weights=None, batch_avg=True):
        """Adversarial constraint function of AAAI'20 paper.

        Args:
            adv_pc (torch.FloatTensor): [B, K, 3]
            ori_pc (torch.FloatTensor): [B, K, 3]
            weights (np.array): weight factors
            batch_avg: (bool, optional): whether to avg over batch dim
        """
        chamfer_loss = self.chamfer_dist(
            adv_pc, ori_pc, weights=weights, batch_avg=batch_avg)
        
        knn_loss = self.knn_dist(
            adv_pc, weights=weights, batch_avg=batch_avg)
        
        loss = chamfer_loss * self.w1 + knn_loss * self.w2
        
        return loss